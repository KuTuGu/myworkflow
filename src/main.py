import gradio as gr
from langfuse import get_client
from smolagents import OpenAIModel, CodeAgent, GradioUI
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import os
from typing import Generator
from smolagents import WebSearchTool, WikipediaSearchTool, VisitWebpageTool, FinalAnswerTool
from tools import MarkItDownTool, DownloadTool

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

langfuse = get_client()
SmolagentsInstrumentor().instrument()

model = OpenAIModel(
    model_id=model_id,
    api_base=api_base,
    api_key=api_key,
    temperature=0.7,
    max_tokens=10000,
    top_p=0.9,
)
markitdown = MarkItDownTool(api_key, api_base, model_id)

agent = CodeAgent(
    model=model, add_base_tools=True,
    instructions="请尽量搜索英语资料，但回答时请始终保持中文",
    tools=[WebSearchTool(), WikipediaSearchTool(), VisitWebpageTool(), FinalAnswerTool(), markitdown, DownloadTool()],
    additional_authorized_imports=["urllib"]
)

class CatchErrorAndMultiModelGradioUI(GradioUI):
    def _stream_response(self, message: str | dict, history: list[dict]) -> Generator:
        try:
            yield from super()._stream_response(message, history)
        except Exception as e:
            self.agent.memory.reset()
            self.agent.monitor.reset()
            yield str(e)

    def _save_uploaded_file(self, file_path: str) -> str:
        """Parse the uploaded file to markdown content using MarkItDownTool."""
        if self.file_upload_folder is None:
            return file_path

        # Use the MarkItDownTool to convert the file
        return markitdown.forward(file_path)

    def _process_message(self, message: str | dict) -> tuple[str, list[str] | None]:
        """Don't need process the file."""
        message, files = super()._process_message(message)
        return message, None

gradio_ui = CatchErrorAndMultiModelGradioUI(agent, file_upload_folder="uploads")
gradio_ui.launch(share=False, server_name="0.0.0.0", server_port=8100)
