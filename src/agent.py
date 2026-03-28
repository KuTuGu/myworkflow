import os
from typing import Callable

from deepagents import CompiledSubAgent
from deepagents.middleware import (
    MemoryMiddleware,
    SkillsMiddleware,
    SubAgentMiddleware,
    create_summarization_tool_middleware,
)
from deepagents_acp.server import AgentSessionContext
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

from agents import (
    ANALYST_AGENT,
    CODER_AGENT,
    PROMPT_OPTIMIZER_AGENT,
    RESEARCHER_AGENT,
    REVIEWER_AGENT,
    TESTER_AGENT,
)
from middlewares import PYTHON_EXECUTOR_PROMPT, PythonExecutorMiddleware
from tools import file_tools, websearch_tools
from tools.file import backend

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]


def build_agent_flow(
    checkpointer: Checkpointer,
    store: BaseStore,
    interrupt_config_by_mode: Callable,
    browser_tools: list[BaseTool],
):
    model = ChatOpenAI(
        model=model_id,
        base_url=api_base,
        api_key=api_key,
    )

    base_middlewares = [
        TodoListMiddleware(),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=50000,
                    clear_tool_inputs=True,
                ),
            ],
        ),
        create_summarization_tool_middleware(model, backend),
    ]

    def build_main_agent(context: AgentSessionContext) -> CompiledStateGraph:
        """Agent factory based in the given root directory."""
        interrupt_config = interrupt_config_by_mode(context.mode)
        base_middlewares.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_config))

        researcher_agent = create_agent(
            name=RESEARCHER_AGENT["name"],
            model=model,
            checkpointer=checkpointer,
            store=store,
            system_prompt=RESEARCHER_AGENT["system_prompt"] + PYTHON_EXECUTOR_PROMPT,
            tools=websearch_tools + browser_tools + file_tools,
            middleware=base_middlewares
            + [
                PythonExecutorMiddleware(),
                SkillsMiddleware(backend=backend, sources=["./src/skills/research"]),
                ModelCallLimitMiddleware(run_limit=30),
            ],
        ).with_config({"recursion_limit": 1_000})

        prompt_optimizer_agent = create_agent(
            name=PROMPT_OPTIMIZER_AGENT["name"],
            model=model,
            checkpointer=checkpointer,
            store=store,
            system_prompt=PROMPT_OPTIMIZER_AGENT["system_prompt"],
            tools=file_tools,
            middleware=base_middlewares
            + [
                ModelCallLimitMiddleware(run_limit=20),
            ],
        ).with_config({"recursion_limit": 100})

        coder_agent = create_agent(
            name=CODER_AGENT["name"],
            model=model,
            checkpointer=checkpointer,
            store=store,
            system_prompt=CODER_AGENT["system_prompt"] + PYTHON_EXECUTOR_PROMPT,
            tools=file_tools,
            middleware=base_middlewares
            + [
                PythonExecutorMiddleware(),
                MemoryMiddleware(
                    backend=backend, sources=["./src/memories/code/AGENTS.md"]
                ),
                SubAgentMiddleware(
                    backend=backend,
                    subagents=[
                        CompiledSubAgent(
                            name=RESEARCHER_AGENT["name"],
                            description=RESEARCHER_AGENT["description"],
                            runnable=researcher_agent,
                        )
                    ],
                ),
                ModelCallLimitMiddleware(run_limit=50),
            ],
        ).with_config({"recursion_limit": 1_000})

        reviewer_agent = create_agent(
            name=REVIEWER_AGENT["name"],
            model=model,
            checkpointer=checkpointer,
            store=store,
            system_prompt=REVIEWER_AGENT["system_prompt"],
            tools=file_tools,
            middleware=base_middlewares
            + [
                SubAgentMiddleware(
                    backend=backend,
                    subagents=[
                        CompiledSubAgent(
                            name=PROMPT_OPTIMIZER_AGENT["name"],
                            description=PROMPT_OPTIMIZER_AGENT["description"],
                            runnable=prompt_optimizer_agent,
                        )
                    ],
                ),
                ModelCallLimitMiddleware(run_limit=20),
            ],
        ).with_config({"recursion_limit": 100})

        tester_agent = create_agent(
            name=TESTER_AGENT["name"],
            model=model,
            checkpointer=checkpointer,
            store=store,
            system_prompt=TESTER_AGENT["system_prompt"] + PYTHON_EXECUTOR_PROMPT,
            tools=file_tools,
            middleware=base_middlewares
            + [
                PythonExecutorMiddleware(),
                SubAgentMiddleware(
                    backend=backend,
                    subagents=[
                        CompiledSubAgent(
                            name=PROMPT_OPTIMIZER_AGENT["name"],
                            description=PROMPT_OPTIMIZER_AGENT["description"],
                            runnable=prompt_optimizer_agent,
                        )
                    ],
                ),
                ModelCallLimitMiddleware(run_limit=30),
            ],
        ).with_config({"recursion_limit": 1_000})

        main_agent = create_agent(
            name="main-agent",
            model=model,
            tools=file_tools,
            middleware=base_middlewares
            + [
                SkillsMiddleware(
                    backend=backend,
                    sources=["./src/skills/assistant", "./src/skills/analysis"],
                ),
                MemoryMiddleware(
                    backend=backend, sources=["./src/memories/assistant/AGENTS.md"]
                ),
                SubAgentMiddleware(
                    backend=backend,
                    subagents=[
                        CompiledSubAgent(
                            name=RESEARCHER_AGENT["name"],
                            description=RESEARCHER_AGENT["description"],
                            runnable=researcher_agent,
                        ),
                        CompiledSubAgent(
                            name=CODER_AGENT["name"],
                            description=CODER_AGENT["description"],
                            runnable=coder_agent,
                        ),
                        CompiledSubAgent(
                            name=REVIEWER_AGENT["name"],
                            description=REVIEWER_AGENT["description"],
                            runnable=reviewer_agent,
                        ),
                        CompiledSubAgent(
                            name=TESTER_AGENT["name"],
                            description=TESTER_AGENT["description"],
                            runnable=tester_agent,
                        ),
                    ],
                ),
            ],
            checkpointer=checkpointer,
            store=store,
            system_prompt="""
                You are user's senior assistant, managing a team of graduate student subagents who specialize in different domains and tasks.
                Your do NOT perform ANY complex tasks yourself. Instead, you coordinate and manage the team to achieve the user’s goals efficiently.
                You act as a coordinator and quality controller, ensuring each subagent’s work aligns with the overall goal and meets high standards.
                Your responsibilities are:
                1. **Understand the user's request** — clarify the goal, scope, and constraints.
                2. **Decompose complex tasks** — break down the request into discrete, executable subtasks.
                3. **Delegate to subagents** — assign each subtask to the most appropriate subagent based on their expertise.
                4. **Synthesize results** — combine the outputs from subagents into a coherent, well-structured final response.
                5. **Quality control** — review subagent outputs for accuracy, completeness, and consistency before presenting them.
                6. **Iterate if needed** — if a subagent’s output is insufficient, refine instructions and delegate again.
            """
            + ANALYST_AGENT["system_prompt"],
        ).with_config({"recursion_limit": 1_000})

        return main_agent

    return build_main_agent
