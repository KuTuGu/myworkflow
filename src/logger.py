from typing import Any, Optional

from deepagents_acp.logger import Logger, UsageDetail
from langfuse import LangfuseOtelSpanAttributes, get_client


class LangfuseLogger(Logger):
    def __init__(self):
        super().__init__()
        self.langfuse = get_client()
        self.active_contexts = {}
        self.last_context = None

    def _on_start(
        self,
        type: str,
        id: Optional[str] = None,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        if type == "agent" or type == "tool" or type == "guardrail":
            observation = self.last_context.start_observation(
                as_type=type,
                name=name,
                input=input,
                output=output,
                metadata=metadata,
            )
            self.active_contexts[id] = {
                "parent": self.last_context,
                "value": observation,
            }
            self.last_context = observation

        else:
            self.last_context.start_observation(
                as_type=type,
                name=name,
                input=input,
                output=output,
                metadata=metadata,
            ).end()

    def _on_end(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        context = self.active_contexts.pop(id)
        self.last_context = context["parent"]
        observation = context["value"]

        observation.update(
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
        observation.end()

    def on_agent_start(
        self,
        id: str,
        name: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
    ) -> None:
        self.last_context = self.langfuse
        self._on_start(
            id=id,
            type="agent",
            name=name,
            input=input,
            output=output,
            metadata=metadata,
        )
        self.last_context._otel_span.set_attribute(
            LangfuseOtelSpanAttributes.AS_ROOT, True
        )

    def on_agent_end(
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
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
        usage_details: Optional[UsageDetail] = None,
    ) -> None:
        self.last_context.start_observation(
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
