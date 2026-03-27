import pickle
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
Store intermediate results and write final results to `result` variable.

# ── 3. Error handling ───────────────────────────────────
Validate outputs. Capture error. Instead of crashing, return a meaningful error message.

# ── 4. Structured output ────────────────────────────────
You can only read one variable value `result`.
Always end with a single output block, prefer JSON.

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
  Act: task.invoke("Implement function A", "coder_agent")
  Observe: ...
  Act: task.invoke("Review code diff", "reviewer_agent")
  Observe: ...
  Act: task.invoke("Test code diff && add new tests", "tester_agent")
  Observe: ...
  Act: task.invoke("optimize coder prompt", "prompt_optimizer_agent")
  Observe: ...
  Act: task.invoke("optimize coder prompt", "prompt_optimizer_agent")
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

> Thought: Since each step is interconnected, and I don't need to know the specifics of the modifications and feedback to determine the workflow, I can complete the task by writing a script, rather than multiple tool calls. Since there is unrelated logic, it's best to use an asynchronous parallel approach.

3. Write script
```python
import asyncio

async def workflow():
    \"""Execute the complete workflow with parallel processing\"""

    # Step 1: Invoke CoderAgent to implement function A
    try:
        print("\n=== Step 1: Invoking CoderAgent ===")
        # No return value
        await task.ainvoke(
            "Please implement function A. <Functional description of A>",
            "coder_agent"
        )
    except Exception as e:
        return str(f"An error occurred during the coding process. {e}")

    # Step 2 & 3: Execute ReviewerAgent and TesterAgent in parallel
    try:
        print("=== Step 2 & 3: Parallel execution of ReviewerAgent and TesterAgent ===")

        # Create tasks for parallel execution
        review_task = asyncio.create_task(
            task.ainvoke("Please review code diff.", "reviewer_agent")
        )
        test_task = asyncio.create_task(
            task.ainvoke("Please test code changes and add new tests.", "tester_agent")
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
            task.ainvoke(
                f"Optimize coder agent prompt based on reviewer feedback: {review_result}",
                "prompt_optimizer_agent"
            )
        )
        optimize_test_task = asyncio.create_task(
            task.ainvoke(
                f"Optimize coder agent prompt based on tester feedback: {test_result}",
                "prompt_optimizer_agent"
            )
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
    result = {
        "code_review": review_result,
        "code_test": test_result,
        "prompt_optimization_review": review_optimization,
        "prompt_optimization_test": test_optimization,
        "status": "success"
    }

# Run the asynchronous workflow
asyncio.run(workflow())
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
  Act: duckduckgo_results_json.invoke("Search item 1-10 on github.com...")
  Observe: ...
  Act: duckduckgo_results_json.invoke("Search item 11-20 on github.com...")
  Observe: ...
  Act: duckduckgo_results_json.invoke("Search item 21-30 on github.com..")
  Observe: ...
  Act: duckduckgo_results_json.invoke("Search item 1-10 on news.ycombinator.com...")
  Observe: ...
  Act: duckduckgo_results_json.invoke("Search item 11-20 on news.ycombinator.com...")
  Observe: ...
  Act: duckduckgo_results_json.invoke("Search item 21-30 on news.ycombinator.com..")
  Observe: ...

✅  Correct (one aggregated script):
```python
import asyncio

async def execute_parallel_searches():
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
        duckduckgo_results_json(query)
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

asyncio.run(execute_parallel_searches())
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

            output_path = base_dir / "output.pkl"

            exec_code = f"""
import pickle

{code.strip()}

_result = locals().get("result", None)
with open({str(output_path)!r}, "wb") as _f:
    pickle.dump(_result, _f)
"""
            exec(exec_code, {"__name__": "__main__", **(tools or {})})

            if output_path.exists():
                with open(output_path, "rb") as f:
                    return pickle.load(f)
            return None

        except Exception as e:
            return str(e)

        finally:
            shutil.rmtree(str(base_dir), ignore_errors=True)

    async def async_python_executor(
        code: str, dependencies: Optional[list[str]] = []
    ) -> Any:
        return python_executor(code, dependencies)

    return StructuredTool.from_function(
        name="python_executor",
        description="""
            Execute any code generated by LLM and support install third-party dependencies, but for speed, please use built-in dependencies whenever possible.
            IMPORTANT: Support invoke any other tools you have. You should prioritize using this tool in combination with other atomic tools to avoid multiple chained calls.

            Returns:
                The variable `result` in the code(if it exists), otherwise it returns None. The `result` support arbitrary Python object.
                For example: python_executor("say('hi'); result = { 'a': 1 }") -> It'll print 'hi' and return { 'a': 1 }
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
            tool.name: tool.func
            for tool in request.tools
            if tool.name != "python_executor"
        }

        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        self.atom_tools = {
            tool.name: tool.func
            for tool in request.tools
            if tool.name != "python_executor"
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
