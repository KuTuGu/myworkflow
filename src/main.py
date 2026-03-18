from langfuse import get_client
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

from ui import CatchErrorAndMultiModelGradioUI
from agent import root_agent

langfuse = get_client()
SmolagentsInstrumentor().instrument()

gradio_ui = CatchErrorAndMultiModelGradioUI(root_agent, file_upload_folder="uploads")
gradio_ui.launch(share=False, server_name="0.0.0.0", server_port=8100)
