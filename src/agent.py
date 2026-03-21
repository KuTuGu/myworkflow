from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents.backends import FilesystemBackend
from langgraph.store.memory import InMemoryStore
from langchain.messages import AIMessage, ToolMessage
from langfuse import get_client
import os
import time
import shutil
import json
from typing import Generator

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

langfuse = get_client(public_key="project_a_key")

model = ChatOpenAI(
    model=model_id,
    base_url=api_base,
    api_key=api_key,
)

agent = create_deep_agent(
    name="main-agent",
    model=model,
    backend=FilesystemBackend(root_dir=os.path.dirname(__file__), virtual_mode=True),
    skills=["/skills"],
    store=InMemoryStore(),
    memory=["/memories/AGENTS.md"],
    system_prompt="""
        You may have some SOUL files at /memories folder with additional instructions and preferences.
        Read them at the start of conversations to understand user preferences.
        When users provide feedback like "please always do X" or "I prefer Y", update them using the edit_file tool.
        IMPORTANT: Unless specified, other files you generate should be stored in the /dist directory!
    """
    # subagents=subagents,
)

# Skip internal middleware steps - only show meaningful node names
INTERESTING_NODES = {"model", "tools"}
def chat(message: str, history: list[dict]) -> Generator:
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
        root_span.update(input={"text": text, "files": files, "msg": msg})

        last_source = ""
        last_tool = ""
        response = ""

        active_tools = {}

        try:
            for chunk in agent.stream(
                {"messages": history + [{"role": "user", "content": msg}]},
                stream_mode=["updates", "messages", "custom"],
                subgraphs=True,
                version="v2",
            ):
                source = "main agent" if not chunk["ns"] else chunk["ns"][-1]
                with open(os.path.join(os.path.dirname(__file__), "memories/log.json"), "a") as f:
                    f.write(str(chunk["ns"]))
                    f.write("\n")
                    f.write(str(chunk["type"]))
                    f.write("\n")
                    f.write(str(chunk["data"]))
                    f.write("\n")
                # if source != last_source:
                #     parent = log_source[-1] if len(log_source) > 0 else root_span
                #     log_source.append(parent.start_as_current_observation(as_type="agent", name=source))
                #     last_source = source

                # logger update
                if chunk["type"] == "updates":
                    for node_name, data in chunk["data"].items():
                        if node_name not in INTERESTING_NODES:
                            langfuse.start_observation(as_type="chain", name=node_name, metadata=data).end()

                        # ─── Phase 1: Detect subagent starting ────────────────────────
                        # When the main agent's model_request contains task tool calls,
                        # a subagent has been spawned.
                        if node_name == "model":
                            for msg in data.get("messages", []):
                                # message
                                if isinstance(msg, AIMessage):
                                    langfuse.start_as_current_observation(
                                        as_type="generation",
                                        name="LLM generate",
                                        metadata=msg.response_metadata,
                                        usage_details={
                                            "input": msg.usage_metadata.get("input_tokens", 0),
                                            "output": msg.usage_metadata.get("output_tokens", 0),
                                            "total": msg.usage_metadata.get("total_tokens", 0),
                                            "cache_read_input_tokens": msg.usage_metadata.get("input_token_details", {}).get("cache_read", 0)
                                        }
                                    )

                                # tool calls
                                for tc in getattr(msg, "tool_calls", []):
                                    active_tools[tc["id"]] = langfuse.start_as_current_observation(
                                        as_type="tool",
                                        name=tc["name"],
                                        input=tc["args"],
                                    )

                        # # ─── Phase 2: Detect subagent running ─────────────────────────
                        # # When we receive events from a tools:UUID namespace, that
                        # # subagent is actively executing.
                        # if chunk["ns"] and chunk["ns"][0].startswith("tools:"):
                        #     pregel_id = chunk["ns"][0].split(":")[1]
                        #     # Check if any pending subagent needs to be marked running.
                        #     # Note: the pregel task ID differs from the tool_call_id,
                        #     # so we mark any pending subagent as running on first subagent event.
                        #     for sub_id, sub in active_tools.items():
                        #         if sub["status"] == "pending":
                        #             sub["status"] = "running"
                        #             print(
                        #                 f'[lifecycle] RUNNING  → subagent "{sub["type"]}" '
                        #                 f"(pregel: {pregel_id})"
                        #             )
                        #             break

                        # ─── Phase 3: Detect subagent completing ──────────────────────
                        # When the main agent's tools node returns a tool message,
                        # the subagent has completed and returned its result.
                        if node_name == "tools":
                            for msg in data.get("messages", []):
                                # tool results
                                if isinstance(msg, ToolMessage):
                                    subtool = active_tools.pop(msg.tool_call_id, None)
                                    if subtool:
                                        subtool.update(output=msg.content)
                                        subtool.end()
                                    else:
                                        print(f"Warning: Subtool {msg.tool_call_id} not found in active_tools.")
                                        print(msg)

                        # root_span.update(output={source: response + node_name})

                # user interface update
                elif chunk["type"] == "messages":
                    token, metadata = chunk["data"]

                    with langfuse.start_as_current_observation(as_type="tool", name="Tool Call", metadata=metadata) as tool:
                        if hasattr(token, 'tool_call_chunks'):
                            for tc in token.tool_call_chunks:
                                if tc.get("name") and len(tc['name']) > 0:
                                    last_tool = tc['name']
                                    tool.update(input={last_tool: ""})
                                if tc.get("args"):
                                    tool.update(input={last_tool: tool.input.get(last_tool, "") + tc["args"]})

                        if token.type == "tool":
                            tool.update(output={token.name: token.content})

                    if isinstance(token, AIMessage) and token.content and len(token.tool_call_chunks) == 0:
                        with langfuse.start_as_current_observation(as_type="generation", name=source) as ge:
                            response += token.content
                            ge.update(output=response)
                        root_span.update(output={source: response})

                # custom event
                elif chunk["type"] == "custom":
                    langfuse.start_observation(as_type="event", name=source, metadata=chunk["data"]).end()

                # yield response

            for tool_id, subtool in active_tools.items():
                print(f"Warning: Subtool {tool_id} still in active_tools.")
                subtool.end()

        except Exception as e:
            yield str(e)



# webbrowser_agent = CodeAgent(
#     additional_authorized_imports=["helium"],
#     tools=browser_tools + file_tools,
#     add_base_tools=True,
#     skills=skills,
#     model=model,
#     step_callbacks=[save_screenshot],
#     name="webbrowser_agent",
#     description="网页浏览者",
#     executor_kwargs=executor_kwargs,
#     verbosity_level=2,
#     instructions=helium_instructions + """
#         你是一个浏览器控制的多模态agent，你可以使用BrowserTool来浏览当前页面、搜索文本、关闭弹窗，返回上一页等；
#         注意：浏览超出屏幕的内容时，优先使用scale_down而不是滚动窗口，只有当scale_down缩小的内容你无法识别时，才考虑滚动窗口；
#         还有不要忘了helium，它为你提供了更多页面操作。
#     """,
# )
# webbrowser_agent.python_executor("from helium import *")
