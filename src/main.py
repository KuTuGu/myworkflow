import gradio as gr
from langfuse import get_client
from smolagents import OpenAIModel, WebSearchTool, CodeAgent, GradioUI
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import os
from ddgs import DDGS

langfuse = get_client()
SmolagentsInstrumentor().instrument()

model = OpenAIModel(
    model_id=os.environ["OPENAI_NAME"],
    api_base=os.environ["OPENAI_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0.7,
    max_tokens=10000,
    top_p=0.9,
)

agent = CodeAgent(
    model=model, tools=[WebSearchTool()], add_base_tools=True,
    instructions="请尽量搜索英语资料，但回答时请始终保持中文"
)

gradio_ui = GradioUI(agent, file_upload_folder="uploads")
gradio_ui.launch(share=False, server_name="0.0.0.0", server_port=8100)
