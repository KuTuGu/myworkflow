import asyncio
import os

from acp import run_agent
from acp.schema import SessionMode, SessionModeState
from deepagents_acp.server import AgentServerACP
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from playwright.async_api import async_playwright

from agent import build_agent_flow
from logger import LangfuseLogger

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

    server = AgentServerACP(
        agent=build_agent_flow(
            checkpointer=checkpointer,
            store=store,
            interrupt_config_by_mode=interrupt_config_by_mode,
            browser_tools=browser_tools,
        ),
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
