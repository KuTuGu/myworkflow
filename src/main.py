from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware import ContextEditingMiddleware, ClearToolUsesEdit
from langchain_community.tools import DuckDuckGoSearchResults
import gradio as gr
from langfuse import get_client
from langfuse.langchain import CallbackHandler
import os
from ddgs import DDGS

langfuse = get_client()
langfuse_handler = CallbackHandler()

model = ChatOpenAI(
    model=os.environ["OPENAI_NAME"],
    max_retries=3,
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_URL"],
    callbacks=[langfuse_handler],
)
agent = create_agent(
    model=model,
    tools=[DuckDuckGoSearchResults()],
    middleware=[
        SummarizationMiddleware(
            model=model,
            trigger=("tokens", 10000),
            keep=("messages", 20),
        ),
        TodoListMiddleware(),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=100000,
                    keep=3,
                ),
            ],
        ),
    ],
    system_prompt="你是一个乐于助人的个人助手，资料搜索尽量找英语资料，除非是国内网站，交流时请始终以中文回答。",
)

def chatbot(msg: str, history: list):
    full = ""
    for chunk in agent.stream(
        {"messages": history + [{"role": "user", "content": msg}]},
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] == "messages":
            token, metadata = chunk["data"]
            if metadata['langgraph_node'] == 'model':
                for block in token.content_blocks:
                    if block["type"] == "text":
                        full += block["text"]
                        yield full

demo = gr.ChatInterface(chatbot)
demo.launch(server_name="0.0.0.0", server_port=8100)
