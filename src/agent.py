from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents.backends import FilesystemBackend
from langgraph.store.memory import InMemoryStore
from langchain.messages import AIMessage, ToolMessage
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_sync_playwright_browser
from langfuse import get_client
import os
import time
import shutil
import json
from typing import Generator

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

langfuse = get_client()

sync_browser = create_sync_playwright_browser()
toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=sync_browser)
browser_tools = toolkit.get_tools()

model = ChatOpenAI(
    model=model_id,
    base_url=api_base,
    api_key=api_key,
)

agent = create_deep_agent(
    name="main-agent",
    model=model,
    tools=[DuckDuckGoSearchResults()],
    backend=FilesystemBackend(root_dir=os.path.dirname(__file__), virtual_mode=True),
    skills=["/skills"],
    store=InMemoryStore(),
    memory=["/memories/AGENTS.md"],
    system_prompt="""
        You may have some SOUL files at /memories folder with additional instructions and preferences.
        Read them at the start of conversations to understand user preferences.
        When users provide feedback like "please always do X" or "I prefer Y", update them using the edit_file tool.
        This line is followed by a long section of SYSTEM_PROMPT. You can proactively optimize it or, based on user feedback,
        after each interaction, using explicit annotations such as IMPORTANT in the SOUL file to accomplish the work more effectively.
        IMPORTANT: Unless specified, other files you generate should be stored in the /dist directory!
    """
)

def chat(message: str | dict, history: list[dict]) -> Generator:
    # gradio edit input format
    if isinstance(message, str):
        message = {"text": message}
    text = message.get("text", "")
    files = message.get("files", [])

    with langfuse.start_as_current_observation(as_type="span", name="user-request") as root_span:
        # Copy files from local to virtual backend
        file_paths = []
        for path in files:
            dest_path = os.path.join(os.path.dirname(__file__), "dist", os.path.basename(path))
            virtual_path = os.path.join("/dist", os.path.basename(path))
            file_paths.append(virtual_path)
            shutil.copy(path, dest_path)
        msg = text + (f"\nYou have been provided with these files: {file_paths}" if len(file_paths) > 0 else "")
        root_span.update(input={"text": text, "files": file_paths, "msg": msg})

        response = ""
        active_tools = {}
        parent = root_span
        try:
            for chunk in agent.stream(
                {"messages": history + [{"role": "user", "content": msg}]},
                stream_mode=["updates", "messages", "custom"],
                subgraphs=True,
                version="v2",
            ):
                # logger
                if chunk["type"] == "updates":
                    for node_name, data in chunk["data"].items():
                        # ───── Detect tool starting ─────
                        if node_name == "model":
                            for msg in data.get("messages", []):
                                # message
                                if isinstance(msg, AIMessage):
                                    parent.start_observation(
                                        as_type="generation",
                                        name="LLM generate",
                                        output=msg.content,
                                        metadata=msg.response_metadata,
                                        usage_details={
                                            "input": msg.usage_metadata.get("input_tokens", 0),
                                            "output": msg.usage_metadata.get("output_tokens", 0),
                                            "total": msg.usage_metadata.get("total_tokens", 0),
                                            "cache_read_input_tokens": msg.usage_metadata.get("input_token_details", {}).get("cache_read", 0)
                                        }
                                    ).end()

                                # tool calls
                                for tc in getattr(msg, "tool_calls", []):
                                    with open(os.path.join(os.path.dirname(__file__), "memories/log2.json"), "a") as f:
                                        f.write(str(tc))
                                        f.write("\n")
                                    active_tools[tc["id"]] = {
                                        "parent": parent,
                                        "observation": parent.start_observation(
                                            as_type="tool",
                                            name=tc["name"],
                                            input=tc["args"],
                                        )
                                    }
                                    parent = active_tools[tc["id"]]["observation"]

                        # ───── Detect tool completing ─────
                        elif node_name == "tools":
                            for msg in data.get("messages", []):
                                # tool output
                                if isinstance(msg, ToolMessage):
                                    tool = active_tools.pop(msg.tool_call_id, None)
                                    if tool:
                                        tool["observation"].update(output=msg.content)
                                        tool["observation"].end()
                                        parent = tool["parent"]
                                    else:
                                        print(f"Warning: Tool {msg.tool_call_id} not found in active_tools.")

                        else:
                            parent.start_observation(as_type="chain", name=node_name, metadata=data).end()

                # user interface update
                elif chunk["type"] == "messages":
                    token, metadata = chunk["data"]

                    if isinstance(token, AIMessage):
                        response += token.content
                        yield response

                # custom event
                elif chunk["type"] == "custom":
                    parent.start_observation(as_type="event", name=chunk["ns"], metadata=chunk["data"]).end()

        except Exception as e:
            yield str(e)
