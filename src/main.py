import gradio as gr
from langfuse import get_client
from smolagents import OpenAIModel, CodeAgent, GradioUI
from smolagents import WebSearchTool, WikipediaSearchTool, VisitWebpageTool
from smolagents import UserInputTool, FinalAnswerTool
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import os
from typing import Generator

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
    model=model, add_base_tools=True,
    instructions="请尽量搜索英语资料，但回答时请始终保持中文",
    tools=[
        WebSearchTool(), WikipediaSearchTool(), VisitWebpageTool(), FinalAnswerTool()
    ],
)

class CatchErrorGradioUI(GradioUI):
    def _stream_response(self, message: str | dict, history: list[dict]) -> Generator:
        try:
            yield from super()._stream_response(message, history)
        except Exception as e:
            self.agent.memory.reset()
            self.agent.monitor.reset()
            yield str(e)

gradio_ui = CatchErrorGradioUI(agent, file_upload_folder="uploads")
gradio_ui.launch(share=False, server_name="0.0.0.0", server_port=8100)
