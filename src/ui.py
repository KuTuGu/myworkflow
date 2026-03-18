import gradio as gr
from smolagents import GradioUI
from typing import Generator

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
        return self.agent.tools["MarkItDownTool"].forward(file_path)

    def _process_message(self, message: str | dict) -> tuple[str, list[str] | None]:
        """Don't need process the file."""
        message, files = super()._process_message(message)
        return message, None
