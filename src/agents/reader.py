from typing import Optional

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_community.tools import DuckDuckGoSearchResults

SYSTEM_PROMPT = """
    You value accuracy, are able to handle various document layouts, and adapt to different content types. When a user provides a file or a URL, you must:
    1. Identify the content type and determine the appropriate parsing approach.
    2. Analyze the content to identify:
    - Key entities (names, dates, locations, organizations)
    - Numerical data, tables, or structured lists
    - Main topics, summaries, or key takeaways
    3. Structure the extracted information into a clear, organized format.
    4. Preserve source references and note any parsing limitations (e.g., scanned images without OCR, paywalled content, dynamic JavaScript-rendered pages).
    IMPORTANT: You should always return the summary information rather than the full content.
"""


def ReaderAgent(tools: Optional[list] = None, middleware: Optional[list] = None):
    return {
        "name": "reader_agent",
        "description": "A specifically reader Agent designed to extract summary information from file paths and URLs",
        "system_prompt": SYSTEM_PROMPT,
        "tools": [DuckDuckGoSearchResults()] + (tools or []),
        "middleware": [
            # ToolRetryMiddleware(),
        ]
        + (middleware or []),
        "skills": ["./src/skills/analysis"],
    }
