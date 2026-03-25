import asyncio
import os

from acp import run_agent
from acp.schema import SessionMode, SessionModeState
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents_acp.server import AgentServerACP, AgentSessionContext
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
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
from logger import LangfuseLogger

workspace = os.environ["WORKSPACE"]

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

database_url_checkpointer = os.environ["DATABASE_URL_CHECKPOINTER"]
database_url_store = os.environ["DATABASE_URL_STORE"]
database_url_history = os.environ["DATABASE_URL_HISTORY"]


def interrupt_config_by_mode(mode_id: str) -> dict:
    """Get interrupt configuration for a given mode."""
    mode_to_interrupt = {
        "ask_before_edits": {
            "delete_file": {"allowed_decisions": ["approve", "reject"]},
            "write_file": {"allowed_decisions": ["approve", "reject"]},
            "edit_file": {"allowed_decisions": ["approve", "edit", "reject"]},
            "execute": {"allowed_decisions": ["approve", "reject"]},
            "coder_agent": {"allowed_decisions": ["approve", "reject"]},
            "tester_agent": {"allowed_decisions": ["approve", "reject"]},
            "prompt_optimizer_agent": {"allowed_decisions": ["approve", "reject"]},
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

    backend = LocalShellBackend(
        root_dir=workspace,
        inherit_env=True,
        virtual_mode=False,
        env=os.environ.copy(),
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

    tool_call_limit_middleware = ToolCallLimitMiddleware(run_limit=10)
    context_edit_middleware = ContextEditingMiddleware(
        edits=[
            ClearToolUsesEdit(
                trigger=50000,
                clear_tool_inputs=True,
            ),
        ],
    )

    def build_agent(context: AgentSessionContext) -> CompiledStateGraph:
        """Agent factory based in the given root directory."""
        interrupt_config = interrupt_config_by_mode(context.mode)

        return create_deep_agent(
            name="llm",
            model=model,
            backend=backend,
            skills=["./src/skills/assistant"],
            store=store,
            interrupt_on=interrupt_config,
            checkpointer=checkpointer,
            memory=["./src/memories/AGENTS.md"],
            middleware=[context_edit_middleware],
            subagents=[
                ReaderAgent(
                    tools=browser_tools,
                    middleware=[
                        context_edit_middleware,
                        tool_call_limit_middleware,
                    ],
                ),
                ResearcherAgent(
                    tools=browser_tools,
                    middleware=[context_edit_middleware, tool_call_limit_middleware],
                ),
                CoderAgent(middleware=[context_edit_middleware]),
                ReviewerAgent(middleware=[context_edit_middleware]),
                TesterAgent(middleware=[context_edit_middleware]),
                PromptOptimizerAgent(middleware=[context_edit_middleware]),
            ],
            system_prompt="""
                You are user's senior assistant, managing a team of graduate student subagents who specialize in different domains and tasks.
                Your do NOT perform complex tasks yourself. Instead, you coordinate and manage the team to achieve the user’s goals efficiently.
                You act as a coordinator and quality controller, ensuring each subagent’s work aligns with the overall goal and meets high standards.
                Your responsibilities are: 1. **Understand the user's request** — clarify the goal, scope, and constraints.
                2. **Decompose complex tasks** — break down the request into discrete, executable subtasks.
                3. **Delegate to subagents** — assign each subtask to the most appropriate subagent based on their expertise.
                4. **Synthesize results** — combine the outputs from subagents into a coherent, well-structured final response.
                5. **Quality control** — review subagent outputs for accuracy, completeness, and consistency before presenting them.
                6. **Iterate if needed** — if a subagent’s output is insufficient, refine instructions and delegate again.
            """,
        )

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
