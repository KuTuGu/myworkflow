"""MarkItDown tool for converting various file types to markdown."""

import os
from typing import Any, Dict, Optional
from smolagents import Tool
from markitdown import MarkItDown
from openai import OpenAI

class MarkItDownTool(Tool):
    """A tool for reading files in Markdown format, supporting any file type(Files, Images, Audios, Youtube-transcription, etc.).
    IMPORTANT!!! Use this tool to read any file, no other ways.
    """
    
    name = "markitdown"
    description = "Reading files in Markdown format, supporting any file type(Files, Images, Audios, Youtube-transcription, etc.)."
    inputs = {
        "file_path": {
            "type": "string", 
            "description": "Local path to the file to read. Don't support url! You should use download tool firstly to get the file."
        },
    }
    output_type = "string"
    
    def __init__(self, api_key: str, api_base: str, model_id: str):
        """Initialize the MarkItDownTool with OpenAI client configuration."""
        super().__init__()
        
        self.md = MarkItDown(
            enable_plugins=True,
            llm_client=OpenAI(
                base_url=api_base,
                api_key=api_key,
            ),
            llm_model=model_id,
        )

    def forward(self, file_path: str) -> str:
        """Read any file."""

        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        
        try:
            result = self.md.convert(file_path)
            return result.text_content
        except Exception as e:
            return f"Error converting file to markdown: {str(e)}"