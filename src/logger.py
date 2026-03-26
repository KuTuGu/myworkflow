from typing import Any, Optional

from deepagents_acp.logger import Logger, UsageDetail
from langfuse import LangfuseOtelSpanAttributes, get_client


class LangfuseLogger(Logger):
    def __init__(self):
        super().__init__()
        self.langfuse = get_client()
        self.active_agents = {}
        self.active_observations = {}
        self.last_agent: Any = None

    def _on_start(
        self,
        type: str,
        id: Optional[str] = None,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self.active_observations[id] = self.last_agent.start_observation(
            as_type=type,
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
        if not (type == "tool" or type == "guardrail"):
            observation = self.active_observations.pop(id)
            observation.end()

    def _on_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        observation = self.active_observations.pop(id)
        observation.update(
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
        observation.end()

    def _on_agent_start(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        observation_ctx = self.langfuse.start_as_current_observation(
            as_type="agent",
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
        observation = observation_ctx.__enter__()
        self.active_agents[id] = {
            "name": name,
            "observation": observation,
            "observation_ctx": observation_ctx,
        }
        self.last_agent = observation

    def _on_agent_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        agent = self.active_agents.pop(id)
        agent["observation"].update(
            name=agent["name"],
            input=input,
            output=output,
            metadata=metadata,
        )
        agent["observation_ctx"].__exit__(None, None, None)

    def on_request_start(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self.llm_output = ""
        self._on_agent_start(id, name, input, output, metadata)
        self.last_agent._otel_span.set_attribute(
            LangfuseOtelSpanAttributes.AS_ROOT, True
        )

    def on_request_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self._on_agent_end(
            id=id,
            name=name,
            input=input,
            output=self.llm_output,
            metadata=metadata,
        )

    def on_middleware(
        self,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self._on_start(
            type="chain",
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )

    def on_llm(
        self,
        name: Optional[str] = None,
        model: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[str] = None,
        metadata: Optional[Any] = None,
        usage_details: Optional[UsageDetail] = None,
    ) -> None:
        self.llm_output += output or ""
        self.last_agent.start_observation(
            as_type="generation",
            name=name,
            model=model,
            input=input,
            output=output,
            metadata=metadata,
            usage_details=usage_details,
        ).end()

    def on_tool_start(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        if name == "task":
            subagent_name = metadata["args"]["subagent_type"]
            self.llm_output += (
                f"\n<SubAgent Invoke>{subagent_name}: {input}<SubAgent Invoke>\n"
            )
            self._on_agent_start(
                id=id,
                name=subagent_name,
                input=input,
                output=output,
                metadata=metadata,
            )

        else:
            self.llm_output += f"\n<Tool Call>{name}: {input}<Tool Call>\n"
            self._on_start(
                id=id,
                type="tool",
                name=name,
                input=input,
                output=output,
                metadata=metadata,
            )

    def on_tool_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        if id in self.active_agents:
            agent = self.active_agents[id]
            self.llm_output += (
                f"\n<SubAgent Result>{agent['name']}: {output}<SubAgent Result>\n"
            )
            self._on_agent_end(
                id=id,
                name=agent["name"],
                input=input,
                output=output,
                metadata=metadata,
            )

        else:
            self.llm_output += f"\n<Tool Result>{name}: {output}<Tool Result>\n"
            self._on_end(
                id=id,
                name=name,
                input=input,
                output=output,
                metadata=metadata,
            )

    def on_interrupt_start(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self._on_start(
            id=id,
            type="guardrail",
            name="interrupt",
            input=input,
            output=output,
            metadata=metadata,
        )

    def on_interrupt_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self._on_end(
            id=id,
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
