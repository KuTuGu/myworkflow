import asyncio
import os

from acp import run_agent
from acp.schema import SessionMode, SessionModeState
from deepagents.backends import CompositeBackend, LocalShellBackend, StoreBackend
from deepagents_acp.server import AgentServerACP, AgentSessionContext
from langchain.agents.middleware import (
    ContextEditingMiddleware,
    LLMToolSelectorMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres import PostgresStore
from playwright.async_api import async_playwright

from deepagents import create_deep_agent
from logger import LangfuseLogger
from middlewares import LocalContextMiddleware

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
        },
        "accept_edits": {
            "execute": {"allowed_decisions": ["approve", "reject"]},
        },
        "accept_everything": {},
    }
    return mode_to_interrupt.get(mode_id, {})


async def main() -> None:
    langfuse = LangfuseLogger()

    browser = await async_playwright().start()
    async_browser = await browser.chromium.launch(headless=True)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    browser_tools = toolkit.get_tools()

    store_ctx = PostgresStore.from_conn_string(database_url_store)
    store = store_ctx.__enter__()
    store.setup()

    checkpointer = MemorySaver()

    def build_agent(context: AgentSessionContext) -> CompiledStateGraph:
        """Agent factory based in the given root directory."""
        interrupt_config = interrupt_config_by_mode(context.mode)

        model = ChatOpenAI(
            model=model_id,
            base_url=api_base,
            api_key=api_key,
        )

        backend = LocalShellBackend(
            root_dir="/",
            inherit_env=True,
            virtual_mode=False,
            env=os.environ.copy(),
            timeout=1200,  # 20 min
            max_output_bytes=1_000_000,  # 0.1 M
        )

        return create_deep_agent(
            name="llm",
            model=model,
            tools=[DuckDuckGoSearchResults()] + browser_tools,
            backend=backend,
            skills=["/skills"],
            store=store,
            interrupt_on=interrupt_config,
            checkpointer=checkpointer,
            memory=["/memories/AGENTS.md"],
            middleware=[
                # LLMToolSelectorMiddleware(),  # 默认无限工具
                ToolRetryMiddleware(),
                ModelRetryMiddleware(),
                ContextEditingMiddleware(),
                LocalContextMiddleware(backend),
            ],
            system_prompt="""
                You may have some SOUL files at /memories folder with additional instructions and preferences.
                Read them at the start of conversations to understand user preferences.
                When users provide feedback like "please always do X" or "I prefer Y", update them using the edit_file tool.
                This line is followed by a long section of SYSTEM_PROMPT. You can proactively optimize it or, based on user feedback,
                after each interaction, using explicit annotations such as IMPORTANT in the SOUL file to accomplish the work more effectively.
                IMPORTANT: Unless specified, other files you generate should be stored in the /dist directory!
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


if __name__ == "__main__":
    asyncio.run(main())
