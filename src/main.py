import asyncio
import os
from typing import Any, Optional

from acp import run_agent
from acp.schema import SessionMode, SessionModeState
from deepagents import CompiledSubAgent
from deepagents.backends import StoreBackend
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.subagents import SubAgentMiddleware
from deepagents.middleware.summarization import create_summarization_middleware
from deepagents_acp.server import AgentServerACP, AgentSessionContext
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain.tools import tool
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.utilities import (
    DuckDuckGoSearchAPIWrapper,
    GoogleSerperAPIWrapper,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres.aio import AsyncPostgresStore
from playwright.async_api import async_playwright

from agents import (
    CoderAgent,
    PromptOptimizerAgent,
    ReaderAgent,
    ResearcherAgent,
    ReviewerAgent,
    TesterAgent,
)
from executor import PYTHON_EXECUTOR_PROMPT, PythonExecutorMiddleware
from logger import LangfuseLogger

workspace = os.environ["WORKSPACE"]

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

database_url_checkpointer = os.environ["DATABASE_URL_CHECKPOINTER"]
database_url_store = os.environ["DATABASE_URL_STORE"]
database_url_history = os.environ["DATABASE_URL_HISTORY"]


@tool
def websearch_tool(
    query: str,
    type: Optional[str] = "text",
    ask: Optional[bool] = False,
    google: Optional[bool] = True,
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    **kwargs,
) -> Any:
    """
    web search tool.

    Args:
        query: query string.
        type: search type. Options: Google: "news", "search", "places", "images"| DDGS: "text", "news", "images", Default "search" | "text"
        ask: Quick question and answer, result without additional metadata. Options: bool, Default False
        google: using google or ddgs. Options: bool, Default True
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.
    """
    if google and os.environ.get("SERPER_API_KEY", None):
        websearch_tool = GoogleSerperAPIWrapper(
            type=type, tbs=timelimit, k=max_results, **kwargs
        )
    else:
        websearch_tool = DuckDuckGoSearchAPIWrapper(
            source=type, time=timelimit, max_results=max_results, **kwargs
        )

    if ask:
        return websearch_tool.run(query)
    return websearch_tool.results(query)


def interrupt_config_by_mode(mode_id: str) -> dict:
    """Get interrupt configuration for a given mode."""
    mode_to_interrupt = {
        "ask_before_edits": {
            "delete_file": {"allowed_decisions": ["approve", "reject"]},
            "write_file": {"allowed_decisions": ["approve", "reject"]},
            "edit_file": {"allowed_decisions": ["approve", "edit", "reject"]},
            "execute": {"allowed_decisions": ["approve", "reject"]},
        },
        "accept_edits": {
            "execute": {"allowed_decisions": ["approve", "reject"]},
        },
        "accept_everything": {},
    }
    return mode_to_interrupt.get(mode_id, {})


async def main() -> None:
    langfuse = LangfuseLogger()

    model = ChatOpenAI(
        model=model_id,
        base_url=api_base,
        api_key=api_key,
    )

    store_ctx = AsyncPostgresStore.from_conn_string(database_url_store)
    store = await store_ctx.__aenter__()
    await store.setup()

    checkpointer_ctx = AsyncPostgresSaver.from_conn_string(database_url_checkpointer)
    checkpointer = await checkpointer_ctx.__aenter__()
    await checkpointer.setup()

    browser = await async_playwright().start()
    async_browser = await browser.chromium.launch(headless=True)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    browser_tools = toolkit.get_tools()

    backend = lambda rt: StoreBackend(rt)
    base_middlewares = [
        TodoListMiddleware(),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=50000,
                    clear_tool_inputs=True,
                ),
            ],
        ),
        ModelCallLimitMiddleware(run_limit=20),
        create_summarization_middleware(model, backend),
        PatchToolCallsMiddleware(),
    ]

    def build_subagent(
        metadata: dict,
        tools: Optional[list] = None,
        middleware: Optional[list] = None,
    ) -> dict:
        middlewares = []
        if "skills" in metadata:
            middlewares.append(
                SkillsMiddleware(backend=backend, sources=metadata["skills"])
            )
        if "memories" in metadata:
            middlewares.append(
                MemoryMiddleware(backend=backend, sources=metadata["memories"])
            )
        middlewares.append(PythonExecutorMiddleware())

        agent = create_agent(
            name=metadata["name"],
            model=model,
            tools=(tools or []),
            middleware=middlewares + (middleware or []),
            checkpointer=checkpointer,
            store=store,
            system_prompt=metadata["system_prompt"] + PYTHON_EXECUTOR_PROMPT,
        ).with_config({"recursion_limit": 100})

        return CompiledSubAgent(
            name=metadata["name"],
            description=metadata["description"],
            runnable=agent,
        )

    def build_agent(context: AgentSessionContext) -> CompiledStateGraph:
        """Agent factory based in the given root directory."""
        interrupt_config = interrupt_config_by_mode(context.mode)
        base_middlewares.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_config))

        agent = create_agent(
            name="main-agent",
            model=model,
            middleware=base_middlewares
            + [
                SkillsMiddleware(backend=backend, sources=["./src/skills/assistant"]),
                MemoryMiddleware(backend=backend, sources=["./src/memories/"]),
                SubAgentMiddleware(
                    backend=backend,
                    subagents=[
                        build_subagent(
                            ReaderAgent(),
                            tools=[websearch_tool] + browser_tools,
                            middleware=base_middlewares,
                        ),
                        build_subagent(
                            ResearcherAgent(),
                            tools=[websearch_tool] + browser_tools,
                            middleware=base_middlewares,
                        ),
                        build_subagent(CoderAgent(), middleware=base_middlewares),
                        build_subagent(ReviewerAgent(), middleware=base_middlewares),
                        build_subagent(TesterAgent(), middleware=base_middlewares),
                        build_subagent(
                            PromptOptimizerAgent(), middleware=base_middlewares
                        ),
                    ],
                ),
            ],
            checkpointer=checkpointer,
            store=store,
            system_prompt="""
                You are user's senior assistant, managing a team of graduate student subagents who specialize in different domains and tasks.
                Your do NOT perform ANY complex tasks yourself. Instead, you coordinate and manage the team to achieve the user’s goals efficiently.
                You act as a coordinator and quality controller, ensuring each subagent’s work aligns with the overall goal and meets high standards.
                Your responsibilities are:
                1. **Understand the user's request** — clarify the goal, scope, and constraints.
                2. **Decompose complex tasks** — break down the request into discrete, executable subtasks.
                3. **Delegate to subagents** — assign each subtask to the most appropriate subagent based on their expertise.
                4. **Synthesize results** — combine the outputs from subagents into a coherent, well-structured final response.
                5. **Quality control** — review subagent outputs for accuracy, completeness, and consistency before presenting them.
                6. **Iterate if needed** — if a subagent’s output is insufficient, refine instructions and delegate again.
            """,
        ).with_config({"recursion_limit": 10_000})

        return agent

    server = AgentServerACP(
        agent=build_agent,
        logger=langfuse,
        modes=SessionModeState(
            current_mode_id="ask_before_edits",
            available_modes=[
                SessionMode(
                    id="ask_before_edits",
                    name="Ask before edits",
                    description="Ask permission before edits, writes, shell commands, and plans",
                ),
                SessionMode(
                    id="accept_edits",
                    name="Accept edits",
                    description="Auto-accept edit operations, but ask before shell commands and plans",
                ),
                SessionMode(
                    id="accept_everything",
                    name="Accept everything",
                    description="Auto-accept all operations without asking permission",
                ),
            ],
        ),
    )

    await run_agent(server)

    await store_ctx.__aexit__(None, None, None)
    await checkpointer_ctx.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
