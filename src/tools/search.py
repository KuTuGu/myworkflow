from datetime import datetime
from typing import Optional, TypedDict

from langchain.tools import tool
from langchain_community.utilities import (
    DuckDuckGoSearchAPIWrapper,
    GoogleSerperAPIWrapper,
)


class OrganicResult(TypedDict):
    title: str
    link: str
    snippet: str
    position: int
    date: Optional[str]


class GoogleSearchJSON(TypedDict):
    organic: list[OrganicResult]


class DDGSResult(TypedDict):
    snippet: str
    title: str
    link: str


@tool
def current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Retrieve the current time. You MUST call this before searching real time information.

    Args:
        format: format time string, default "%Y-%m-%d %H:%M:%S".

    Return: time format string
    """
    return datetime.now().strftime(format)


@tool
def google_search_json(
    query: str,
    type: Optional[str] = "search",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    **kwargs,
) -> GoogleSearchJSON:
    """
    google web search json detail tool.

    Args:
        query: query string.
        type: search type. Options: "news", "search", "places", "images", Default "search"
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.

    Return: GoogleSearchJSON
    ```python
        class OrganicResult(TypedDict):
            title: str
            link: str
            snippet: str
            position: int
            date: Optional[str]


        class GoogleSearchJSON(TypedDict):
            organic: list[OrganicResult]
    ```
    """
    websearch_tool = GoogleSerperAPIWrapper(
        type=type, tbs=timelimit, k=max_results, **kwargs
    )

    return websearch_tool.results(query)


@tool
def google_question_ask(
    query: str,
    type: Optional[str] = "search",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    **kwargs,
) -> str:
    """
    google web search question answer tool, result without additional metadata

    Args:
        query: query string.
        type: search type. Options: "news", "search", "places", "images", Default "search"
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.

    Return: str
    """
    websearch_tool = GoogleSerperAPIWrapper(
        type=type, tbs=timelimit, k=max_results, **kwargs
    )
    return websearch_tool.run(query)


@tool
def ddgs_search_json(
    query: str,
    type: Optional[str] = "text",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    **kwargs,
) -> list[DDGSResult]:
    """
    web search tool.

    Args:
        query: query string.
        type: search type. Options "text", "news", "images", Default "text"
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.

    Return: list[DDGSResult]
    ```python
        class DDGSResult(TypedDict):
            snippet: str
            title: str
            link: str
    ```
    """
    websearch_tool = DuckDuckGoSearchAPIWrapper(source=type, time=timelimit, **kwargs)

    return websearch_tool.results(query, max_results)


@tool
def ddgs_question_ask(
    query: str,
    type: Optional[str] = "text",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    **kwargs,
) -> str:
    """
    web search tool.

    Args:
        query: query string.
        type: search type. Options: "text", "news", "images", Default "text"
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.

    Return: str
    """
    websearch_tool = DuckDuckGoSearchAPIWrapper(
        source=type, time=timelimit, max_results=max_results, **kwargs
    )

    return websearch_tool.run(query)
