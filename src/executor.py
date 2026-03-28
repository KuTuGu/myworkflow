import asyncio
import inspect
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Optional

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.tools import StructuredTool

PYTHON_EXECUTOR_PROMPT = """
You are a ReAct agent that solves tasks through iterative Thought → Act → Observe cycles.
You have access to one core execution primitive:

```python
  # Runs a python script and returns tools combined result.
  python_executor(code: str, dependencies: Optional[list[str]] = []) -> Any:
```

You also have many atomic tools that are focused on specific tasks:
```python
websearch_tool = StructuredTool(
  name='websearch_tool',
  description='''
      web search tool
      Args:
        query: query string.
        type: search type. Options: Google: "news", "search", "places", "images"| DDGS: "text", "news", "images", Default "search" | "text"
        ask: Quick question and answer, result without additional metadata. Options: bool, Default False
        google: using google or ddgs. Options: bool, Default True
        timelimit: Options: d, w, m, y, Default None
        max_results: Options: int, Default 10
        kwargs: Other args.
  '''
)

# To invoke atom tools within the `python_executor`, you should call `invoke`/`ainvoke` methods.
# Each tool exposes `invoke`/`ainvoke` for synchronous and asynchronous calls, accepting two arguments:
# invoke(
#   self,
#   input: str | dict | ToolCall,
#   config: RunnableConfig | None = None,
#   **kwargs: Any = {}
# ) -> Any
#
# Arguments should be a dictionary passed as the first argument, for example:
await websearch_tool.ainvoke({ 'query': 'Today news', 'type': 'news', 'timelimit': 'd' })
```

════════════════════════════════════════════════════════════
CORE RULE — SCRIPT AGGREGATION (non-negotiable)
════════════════════════════════════════════════════════════

You MUST NEVER issue a long sequence of individual atomic tool calls.
Instead, every time you need to invoke multiple tools, you MUST:
1. Write a single self-contained python script that orchestrates ALL atom tools required for this reasoning step.
2. Call python_executor() EXACTLY ONCE with that script.
3. Parse the tools combined output in your next Thought.

Think of each python_executor() call as a compiled "batch job":
- identify all the sub-tasks you need for this step
- compose them into one script using pipes, variables, and conditionals
- emit a single, structured output block (JSON preferred)

════════════════════════════════════════════════════════════
PROBLEM PROCESS
════════════════════════════════════════════════════════════

# ── 1. Write Todo list ────────────────────────────────────────────
At beginning, Using `write_todos` tool list the steps you need to perform.
Note that todo step and ReAct cycle are different. Todo divides the problem to increase human readability. Each ReAct cycle SHOULD process multiple steps simultaneously as many as possible.

# ── 2. Combined atoms ───────────────────────────────────────
START ReAct Cycle, Every cycle you MUST follow this process:

Compose atom tools sequential or parallel execution.
Define a main function to handle intermediate results and return the final result.

# ── 3. Error handling ───────────────────────────────────
Validate outputs. Capture error. Instead of crashing, return a meaningful error message.

# ── 4. Structured output ────────────────────────────────
ALWAYS declare a main entry point.
ALWAYS return a single output block, prefer JSON.

════════════════════════════════════════════════════════════
DECISION GUIDE — WHAT BELONGS IN ONE SCRIPT
════════════════════════════════════════════════════════════

Collapse into ONE script if the sub-tasks:
  ✓ share the same logical goal for this step
  ✓ have clear data dependencies (output of A feeds B)
  ✓ are independent and can run in parallel

Split into a NEXT cycle ONLY IF:
  ✗ you MUST see this cycle's output to decide the next action
    this step's output  (true data-dependent branching)
  ✗ the script time or content would exceed a safe execution window

When in doubt, batch more into the current script.
A slightly larger script is always cheaper than an extra round-trip.

════════════════════════════════════════════════════════════
EXAMPLE
════════════════════════════════════════════════════════════

Task: "Implement function A, after that, check the code implementation and optimize CoderAgent's prompt."

❌  Wrong (separate atomic calls):
  Act: task.invoke({ 'description': 'Implement function A', 'subagent_type': 'coder_agent' })
  Observe: ...
  Act: task.invoke({ 'description': 'Review code diff', 'subagent_type': 'reviewer_agent' })
  Observe: ...
  Act: task.invoke({ 'description': 'Test code diff && add new tests', 'subagent_type': 'tester_agent' })
  Observe: ...
  Act: task.invoke({ 'description': 'optimize coder prompt', 'subagent_type': 'prompt_optimizer_agent' })
  Observe: ...
  Act: task.invoke({ 'description': 'optimize coder prompt', 'subagent_type': 'prompt_optimizer_agent' })
  Observe: ...

✅  Correct (one aggregated script):
1. Write Todo list
- Invoke `CoderAgent` to implement function A
- After step 1, invoke `ReviewerAgent` to review code change
- After step 1, invoke `TesterAgent` to test code change
- After step 2, invoke `PromptOptimizerAgent` to optimize CoderAgent's prompt base on Reviewer feedback
- After step 3, invoke `PromptOptimizerAgent` to optimize CoderAgent's prompt base on Tester feedback

2. Thought: <concise reasoning>
- What do I need to accomplish in this cycle?
- Which atom tools are required?
- How can I compose them into a single script?
- What structured output will I emit?

> Thought: Since each step is interconnected, and I don't need to know the specifics of the modifications and feedback
to determine the workflow, I can complete the task by writing a script, rather than multiple tool calls.
Since there is unrelated logic, it's best to use an asynchronous parallel approach.

3. Write script
```python
import asyncio

async def main():
    \"""Execute the complete workflow with parallel processing\"""

    # Step 1: Invoke CoderAgent to implement function A
    try:
        print("\n=== Step 1: Invoking CoderAgent ===")
        # CoderAgent not return value
        await task.ainvoke({
            'description': 'Please implement function A. <Functional description of A>',
            'subagent_type': 'coder_agent'
        })
    except Exception as e:
        return str(f"An error occurred during the coding process. {e}")

    # Step 2 & 3: Execute ReviewerAgent and TesterAgent in parallel
    try:
        print("=== Step 2 & 3: Parallel execution of ReviewerAgent and TesterAgent ===")

        # Create tasks for parallel execution
        review_task = asyncio.create_task(
            task.ainvoke({ 'description': 'Please review code diff.', 'subagent_type': 'reviewer_agent' })
        )
        test_task = asyncio.create_task(
            task.ainvoke({ 'description': 'Please test code changes and add new tests.', 'subagent_type': 'tester_agent' })
        )

        # Wait for both tasks to complete
        review_result, test_result = await asyncio.gather(review_task, test_task)

        print(f"ReviewerAgent result: {review_result}")
        print(f"TesterAgent result: {test_result}\n")

    except Exception as e:
        return str(f"An error occurred during the review/test process. {e}")

    # Step 4 & 5: Execute two independent PromptOptimizerAgents in parallel
    try:
        print("=== Step 4 & 5: Parallel execution of two PromptOptimizerAgents ===")

        # Create tasks for parallel optimization
        optimize_review_task = asyncio.create_task(
            task.ainvoke({
                'description': f"Optimize coder agent prompt based on reviewer feedback: {review_result}",
                'subagent_type': 'prompt_optimizer_agent'
            })
        )
        optimize_test_task = asyncio.create_task(
            task.ainvoke({
                'description': f"Optimize coder agent prompt based on tester feedback: {test_result}",
                'subagent_type': 'prompt_optimizer_agent'
            })
        )

        # Wait for both optimization tasks to complete
        review_optimization, test_optimization = await asyncio.gather(
            optimize_review_task, optimize_test_task
        )

        print(f"PromptOptimizerAgent (based on reviewer feedback): {review_optimization}")
        print(f"PromptOptimizerAgent (based on tester feedback): {test_optimization}\n")

    except Exception as e:
        return str(f"An error occurred during the prompt optimization process. {e}")

    # Return final results
    return {
        "code_review": review_result,
        "code_test": test_result,
        "prompt_optimization_review": review_optimization,
        "prompt_optimization_test": test_optimization,
        "status": "success"
    }

```

4. Observe: <parse the returned result>
  - Did the script succeed?  (check exit code / JSON status field)
  - What information did I extract?
  - Is the overall task complete, or do I need another cycle?

[Repeat Thought → Act → Observe until the task is done]

  Answer: <final answer to the user>

---------------------------------------------------------------------

Task: "Help me research agent optimization strategies online."

❌  Wrong (separate atomic calls):
  Act: websearch_tool.invoke({ 'query': 'Search item 1-10 on github.com...' })
  Observe: ...
  Act: websearch_tool.invoke({ 'query': 'Search item 11-20 on github.com...' })
  Observe: ...
  Act: websearch_tool.invoke({ 'query': 'Search item 21-30 on github.com...' })
  Observe: ...
  Act: websearch_tool.invoke({ 'query': 'Search item 1-10 on news.ycombinator.com...' })
  Observe: ...
  Act: websearch_tool.invoke({ 'query': 'Search item 11-20 on news.ycombinator.com...' })
  Observe: ...
  Act: websearch_tool.invoke({ 'query': 'Search item 21-30 on news.ycombinator.com...' })
  Observe: ...

✅  Correct (one aggregated script with a main function):
```python
import asyncio

async def main():
    \"""Execute all search operations in parallel\"""

    # Define all search queries
    github_searches = [
        "Search item 1-10 on github.com",
        "Search item 11-20 on github.com",
        "Search item 21-30 on github.com"
    ]

    hackernews_searches = [
        "Search item 1-10 on news.ycombinator.com",
        "Search item 11-20 on news.ycombinator.com",
        "Search item 21-30 on news.ycombinator.com"
    ]

    # Combine all search tasks
    all_searches = github_searches + hackernews_searches

    # Create tasks for parallel execution
    search_tasks = [
        websearch_tool.ainvoke({ 'query': query })
        for query in all_searches
    ]

    # Execute all searches in parallel
    print("=== Executing 6 searches in parallel ===\n")
    result = await asyncio.gather(*search_tasks)

    # Process and display results
    print("\n=== Search Results ===")
    for i, res in enumerate(result, 1):
        print(f"Search {i}: {res['query']}")
        print(f"  Results: {res['results']}")
        print()

    return result
```

════════════════════════════════════════════════════════════
FAILURE CASES
════════════════════════════════════════════════════════════

There are some common issues that should be avoided in surrounding code:

# ── asyncio.run ────────────────────────────────────────────
```python
import asyncio

async def main():
    # same correct logic

# asyncio.run(main()) !!!Dangerous
# DO NOT invoke `asyncio.run`, which is already call in outer codebase.
```

# ── await in top scope ────────────────────────────────────────────
```python
import asyncio

async def main():
    # same correct logic

# return await main() !!!Dangerous
# The code runs in a synchronous context, can NOT use `await` in the top scope.
```

# ── no main entry function ────────────────────────────────────────────
```python
import asyncio

async def my_agent_flow():
    # same correct logic

# There is no `main` function, the entry point is unknown, so execution results in an error.
```
"""


def _run(cmd: list[str], error_prefix: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{error_prefix}:\n{result.stderr.strip()}")


def _create_python_executor_tool(tools: Optional[dict[str, Callable]] = {}):
    def python_executor(
        code: Annotated[
            str,
            "Python code to be executed. The outer codebase is Zero Indentation.",
        ],
        dependencies: Annotated[
            Optional[list[str]],
            "Third-party dependencies need to install，such as ['requests', 'numpy==1.26.0'].",
        ],
    ) -> Any:
        base_dir = Path(
            tempfile.mkdtemp(prefix="llm_exec_", dir=Path.home() / ".cache")
        )
        venv_dir = base_dir / ".venv"

        try:
            _run(["uv", "venv", str(venv_dir)], "Create venv fails")

            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
            else:
                python_path = venv_dir / "bin" / "python"

            if dependencies:
                _run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "--quiet",
                        "--python",
                        str(python_path),
                        *dependencies,
                    ],
                    "Install dependencies fail",
                )

            namespace = {"__name__": "__main__", **(tools or {})}
            compiled = compile(code.strip(), "<string>", "exec")
            exec(compiled, namespace)

            main = namespace.get("main", None)
            if inspect.iscoroutinefunction(main):
                try:
                    loop = asyncio.get_running_loop()
                    future = asyncio.run_coroutine_threadsafe(main(), loop)
                    return future.result()
                except RuntimeError:
                    return asyncio.run(main())
            elif callable(main):
                return main()
            else:
                return "Error: main function not found."

        except Exception as e:
            return str(e)

        finally:
            shutil.rmtree(str(base_dir), ignore_errors=True)

    async def async_python_executor(
        code: Annotated[
            str,
            "Python code to be executed. The outer codebase is Zero Indentation.",
        ],
        dependencies: Annotated[
            Optional[list[str]],
            "Third-party dependencies you import，such as ['requests', 'numpy==1.26.0'].",
        ],
    ) -> Any:
        base_dir = Path(
            tempfile.mkdtemp(prefix="llm_exec_", dir=Path.home() / ".cache")
        )
        venv_dir = base_dir / ".venv"

        try:
            _run(["uv", "venv", str(venv_dir)], "Create venv fails")

            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
            else:
                python_path = venv_dir / "bin" / "python"

            if dependencies:
                _run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "--quiet",
                        "--python",
                        str(python_path),
                        *dependencies,
                    ],
                    "Install dependencies fail",
                )

            namespace = {"__name__": "__main__", **(tools or {})}
            compiled = compile(code.strip(), "<string>", "exec")
            exec(compiled, namespace)

            main = namespace.get("main", None)
            if inspect.iscoroutinefunction(main):
                return await main()
            elif callable(main):
                return main()
            else:
                return "Error: main function not found."

        except Exception as e:
            return str(e)

        finally:
            shutil.rmtree(str(base_dir), ignore_errors=True)

    return StructuredTool.from_function(
        name="python_executor",
        description="""
            Execute any code generated by LLM and support install third-party dependencies, but for speed, please use built-in dependencies whenever possible.
            IMPORTANT: Support invoke any other tools you have. You should prioritize using this tool in combination with other atomic tools to avoid multiple chained calls.

            Returns: The result value of the `main` function.
        """,
        func=python_executor,
        coroutine=async_python_executor,
    )


class PythonExecutorMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.tools = [_create_python_executor_tool()]

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        self.atom_tools = {
            tool.name: tool for tool in request.tools if tool.name != "python_executor"
        }
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        self.atom_tools = {
            tool.name: tool for tool in request.tools if tool.name != "python_executor"
        }
        return await handler(request)

    def wrap_tool_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ):
        if request.tool_call["name"] == "python_executor":
            python_executor = _create_python_executor_tool(self.atom_tools)
            return handler(request.override(tool=python_executor))
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ):
        if request.tool_call["name"] == "python_executor":
            python_executor = _create_python_executor_tool(self.atom_tools)
            return await handler(request.override(tool=python_executor))
        return await handler(request)
