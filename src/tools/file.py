import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

from deepagents.backends import FilesystemBackend
from langchain.tools import tool


class FileInfo(TypedDict):
    """Structured file listing info.

    Minimal contract used across backends. Only `path` is required.
    Other fields are best-effort and may be absent depending on backend.
    """

    path: str
    """Absolute or relative file path."""

    is_dir: NotRequired[bool]
    """Whether the entry is a directory."""

    size: NotRequired[int]
    """File size in bytes (approximate)."""

    modified_at: NotRequired[str]
    """ISO 8601 timestamp of last modification, if known."""


@dataclass
class LsResult:
    """Result from backend ls operations.

    Attributes:
        error: Error message on failure, None on success.
        entries: List of file info dicts on success, None on failure.
    """

    error: str | None = None
    entries: list["FileInfo"] | None = None


@dataclass
class ReadResult:
    """Result from read operations.

    Attributes:
        error: Error message on failure, None on success.
        file_data: File content as a plain string (utf-8 text or base64-encoded binary) on success, None on failure.
    """

    error: str | None = None
    file_data: str | None = None


@dataclass
class EditResult:
    """Result from create / edit operations.

    Attributes:
        error: Error message on failure, None on success.
        path: Absolute path of created / edited file, None on failure.
    """

    error: str | None = None
    path: str | None = None


@dataclass
class DiffResult:
    """Result from diff operations.

    Attributes:
        error: Error message on failure, None on success.
        path: Absolute path of patch file, None on failure.
    """

    error: str | None = None
    path: str | None = None


workspace = os.environ["WORKSPACE"]
backend = FilesystemBackend(root_dir=workspace, virtual_mode=True)


@tool
def ls(path: str) -> LsResult:
    """List files and directories in the specified directory (non-recursive).

    Args:
        path: Absolute directory path to list files from.

    Returns: LsResult
    ```python
        class FileInfo(TypedDict):
            \"""Structured file listing info.

            Minimal contract used across backends. Only `path` is required.
            Other fields are best-effort and may be absent depending on backend.
            \"""

            path: str
            \"""Absolute or relative file path.\"""

            is_dir: NotRequired[bool]
            \"""Whether the entry is a directory.\"""

            size: NotRequired[int]
            \"""File size in bytes (approximate).\"""

            modified_at: NotRequired[str]
            \"""ISO 8601 timestamp of last modification, if known.\"""

        @dataclass
        class LsResult:
            \"""Result from backend ls operations.

            Attributes:
                error: Error message on failure, None on success.
                entries: List of file info dicts on success, None on failure.
            \"""

            error: str | None = None
            entries: list["FileInfo"] | None = None
    ```
    """
    return backend.ls(path)


@tool
def read(
    file_path: str,
    offset: int = 0,
    limit: int = 99999,
) -> ReadResult:
    """Read file content for the requested line range. Unless specified, you SHOULD ALWAYS read the whole file.

    Args:
        file_path: Absolute or relative file path.
        offset: Line offset to start reading from, default 0.
        limit: Maximum number of lines to read, default 99999.

    Returns: ReadResult with raw (unformatted) content for the requested window.
    ```python
        @dataclass
        class ReadResult:
            \"""Result from backend read operations.

            Attributes:
                error: Error message on failure, None on success.
                file_data: File content as a plain string (utf-8 text or base64-encoded binary) on success, None on failure.
            \"""

            error: str | None = None
            file_data: str | None = None
    ```
    """
    result = backend.read(file_path, offset, limit)
    if hasattr(result, "file_data"):
        result.file_data = result.file_data.get("content", "")
    return result


@tool
def write(
    file_path: str,
    content: str,
) -> EditResult:
    """Create a new file with content.

    Args:
        file_path: Path where the new file will be created.
        content: Text content to write to the file.

    Return: EditResult
    ```python
        @dataclass
        class EditResult:
            \"""Result from create / edit operations.

            Attributes:
                error: Error message on failure, None on success.
                path: Absolute path of created / edited file, None on failure.
            \"""

            error: str | None = None
            path: str | None = None
    ```
    """

    return backend.write(file_path, content)


@tool
def edit(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,  # noqa: FBT001, FBT002
) -> EditResult:
    """Edit a file by replacing string occurrences.

    Args:
        file_path: Path to the file to edit.
        old_string: The text to search for and replace.
        new_string: The replacement text.
        replace_all: If `True`, replace all occurrences. If `False` (default),
            replace only if exactly one occurrence exists.

    Return: EditResult
    ```python
        @dataclass
        class EditResult:
            \"""Result from create / edit operations.

            Attributes:
                error: Error message on failure, None on success.
                path: Absolute path of created / edited file, None on failure.
            \"""

            error: str | None = None
            path: str | None = None
    ```
    """

    return backend.edit(file_path, old_string, new_string, replace_all)


@tool
def diff(file_path: str) -> DiffResult:
    """Generate a git patch file about current code changes.

    Args:
        file_path: Path the patch file will be created.

    Return: DiffResult
    ```python
        @dataclass
        class DiffResult:
            \"""Result from diff operations.

            Attributes:
                error: Error message on failure, None on success.
                path: Absolute path of patch file, None on failure.
            \"""
            error: str | None = None
            path: str | None = None
    ```
    """
    try:
        git_check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=workspace,
        )
        if git_check.returncode != 0:
            return DiffResult(error="Current directory is not a git repository")

        subprocess.run(
            ["git", "add", "."],
            capture_output=True,
            text=True,
            cwd=workspace,
        )
    except Exception as e:
        return DiffResult(error=f"Failed to check git repository: {e}")

    absolute_file = Path(workspace) / file_path
    try:
        write.invoke({"file_path": file_path, "content": ""})
    finally:
        with open(absolute_file, "w", encoding="utf-8") as patch_file:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                stdout=patch_file,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workspace,
            )

            if result.returncode != 0 and result.stderr:
                return DiffResult(error=f"Git diff failed: {result.stderr}")

    if absolute_file.stat().st_size == 0:
        absolute_file.unlink()
        return DiffResult(error="No changes detected, generated patch file is empty")

    return DiffResult(path=str(Path(file_path).absolute()))
