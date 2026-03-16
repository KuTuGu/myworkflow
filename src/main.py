from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
import gradio as gr
from langfuse import Langfuse
from dotenv import dotenv_values
import os
from query import text_search,news_search,image_search

env = dotenv_values('.env')

langfuse = Langfuse(
    secret_key="sk-lf-你的密钥",
    public_key="pk-lf-你的公钥",
    host=env["NEXTAUTH_URL"]
)

model = ChatOpenAI(
    model=env["MODEL_NAME"],
    max_retries=3,
    api_key=env["MODEL_API_KEY"],
    base_url=env["MODEL_URL"],
)
agent = create_agent(
    model=model,
    tools=[text_search,news_search,image_search],
    system_prompt="你是一个乐于助人的个人助手，资料搜索尽量找英语资料，除非是国内网站，交流时请始终以中文回答。",
)

def chatbot(msg: str, history: str):
    stream = model.stream(history + [{"role": "user", "content": msg}])
    full = ""
    for chunk in stream:
        full += chunk.content
        yield full

demo = gr.ChatInterface(chatbot)
demo.launch()
