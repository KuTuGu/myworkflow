from .file import diff, edit, ls, read, write
from .search import (
    current_time,
    ddgs_question_ask,
    ddgs_search_json,
    google_question_ask,
    google_search_json,
)

websearch_tools = [
    current_time,
    ddgs_search_json,
    ddgs_question_ask,
    google_question_ask,
    google_search_json,
]

file_tools = [ls, read, write, edit, diff]
