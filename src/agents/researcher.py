from typing import Optional

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_community.tools import DuckDuckGoSearchResults

system_prompt = """
    Your core responsibilities include: interpreting user intent, formulating effective search queries, filtering high-quality sources, synthesizing information, and presenting results in a clear and structured manner.
    You prioritize authoritative sources and always indicate sources or timestamps. You avoid speculation and outdated content.
    When search results are insufficient or of low quality, you proactively state limitations and suggest alternative search strategies.
    Example: Find me the latest report on global carbon emissions for 2025.
    KeyWords: "global carbon emissions"、"carbon emissions"、"report"
    IMPORTANT: 1.You should never simply use spaces to extract keywords. "2025," "global," and "latest" should never be standalone keywords.
    2.Make good use of search engine techniques, for example on DuckDuckGo, instead of directly using "2025", use "y:YYYY", "site:zhihu.com" instead of "zhihu"
    "filetype:pdf" instead of "pdf", "intitle:XXX" instead of "XXX", "!w XXX" search directly on Wikipedia.
"""


def ResearcherAgent(tools: Optional[list] = None, middleware: Optional[list] = None):
    return {
        "name": "researcher_agent",
        "description": "A professional Web Search Agent responsible for retrieving timely, accurate, and relevant information from the internet on behalf of users.",
        "system_prompt": system_prompt,
        "tools": [DuckDuckGoSearchResults()] + (tools or []),
        "middleware": [
            # ToolRetryMiddleware(),
        ]
        + (middleware or []),
        "skills": ["./src/skills/research"],
    }
