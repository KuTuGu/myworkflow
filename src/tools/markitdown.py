"""MarkItDown tool for converting various file types to markdown."""

import os
from typing import Any, Dict, Optional
from smolagents import Tool
from markitdown import MarkItDown
from openai import OpenAI

class MarkItDownTool(Tool):
    """A tool that converts various file types to markdown using MarkItDown."""
    
    name = "markitdown"
    description = "Convert various file types (PDF, DOCX, PPTX, images, etc.) to markdown format. Useful for reading and processing documents."
    inputs = {
        "file_path": {
            "type": "string", 
            "description": "Local path to the file to convert to markdown. Don't support url! You should use download tool firstly to get the file."
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
        """Convert the specified file to markdown format."""

        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        
        try:
            result = self.md.convert(file_path)
            return result.text_content
        except Exception as e:
            return f"Error converting file to markdown: {str(e)}"