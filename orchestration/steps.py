from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orchestration.contracts import Step


class FetchDataStep(Step):
    def __init__(
        self,
        name: str,
        provider: Any,
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name)
        self.provider = provider
        self.params = params or {}

    async def execute(self, context: Any) -> Any:
        context.logger.info(f"Executing FetchDataStep: {self.name}")
        params = dict(self.params)
        params.update({"correlation_id": context.correlation_id})
        if hasattr(self.provider, "fetch"):
            result = await self.provider.fetch(**params)
        elif callable(self.provider):
            result = await self.provider(**params)
        else:
            raise TypeError(f"Provider {type(self.provider)} is not callable or does not have 'fetch'")
        context.set(f"{self.name}_result", result)
        return result

    async def compensate(self, context: Any) -> None:
        context.logger.info(f"Compensating FetchDataStep: {self.name} (no-op)")


class TransformDataStep(Step):
    def __init__(
        self,
        name: str,
        transform_fn: Callable[[Any], Any],
        input_key: str | None = None,
    ) -> None:
        super().__init__(name)
        self.transform_fn = transform_fn
        self.input_key = input_key

    async def execute(self, context: Any) -> Any:
        context.logger.info(f"Executing TransformDataStep: {self.name}")
        input_data = context.get(self.input_key) if self.input_key else context.data
        if callable(self.transform_fn):
            result = self.transform_fn(input_data)
        else:
            raise TypeError(f"transform_fn {type(self.transform_fn)} is not callable")
        context.set(f"{self.name}_result", result)
        return result

    async def compensate(self, context: Any) -> None:
        context.logger.info(f"Compensating TransformDataStep: {self.name}")
        result_key = f"{self.name}_result"
        if result_key in context.data:
            del context.data[result_key]


class ValidateDataStep(Step):
    def __init__(
        self,
        name: str,
        validator_fn: Callable[[Any], bool],
        input_key: str | None = None,
        error_message: str = "Validation failed",
    ) -> None:
        super().__init__(name)
        self.validator_fn = validator_fn
        self.input_key = input_key
        self.error_message = error_message

    async def execute(self, context: Any) -> Any:
        context.logger.info(f"Executing ValidateDataStep: {self.name}")
        input_data = context.get(self.input_key) if self.input_key else context.data
        is_valid = self.validator_fn(input_data)
        if not is_valid:
            raise ValueError(self.error_message)
        context.set(f"{self.name}_result", True)
        return input_data

    async def compensate(self, context: Any) -> None:
        context.logger.info(f"Compensating ValidateDataStep: {self.name} (no-op)")


class PersistDataStep(Step):
    def __init__(
        self,
        name: str,
        repository: Any,
        input_key: str | None = None,
        persist_method: str = "save",
    ) -> None:
        super().__init__(name)
        self.repository = repository
        self.input_key = input_key
        self.persist_method = persist_method

    async def execute(self, context: Any) -> Any:
        context.logger.info(f"Executing PersistDataStep: {self.name}")
        input_data = context.get(self.input_key) if self.input_key else context.data
        if hasattr(self.repository, self.persist_method):
            method = getattr(self.repository, self.persist_method)
            if callable(method):
                result = await method(input_data)
            else:
                raise TypeError(f"{self.persist_method} on repository is not callable")
        else:
            raise AttributeError(f"Repository {type(self.repository)} has no method '{self.persist_method}'")
        context.set(f"{self.name}_result", result)
        return result

    async def compensate(self, context: Any) -> None:
        context.logger.info(f"Compensating PersistDataStep: {self.name}")
        if hasattr(self.repository, "delete"):
            persisted = context.get(f"{self.name}_result")
            if persisted and callable(self.repository.delete):
                await self.repository.delete(persisted)


class NotifyStep(Step):
    def __init__(
        self,
        name: str,
        channel: Any,
        message_template: str = "",
        subject: str = "",
    ) -> None:
        super().__init__(name)
        self.channel = channel
        self.message_template = message_template
        self.subject = subject

    async def execute(self, context: Any) -> Any:
        context.logger.info(f"Executing NotifyStep: {self.name}")
        message = self.message_template
        for key, value in context.data.items():
            placeholder = "{" + key + "}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        subject = self.subject
        for key, value in context.data.items():
            placeholder = "{" + key + "}"
            if placeholder in subject:
                subject = subject.replace(placeholder, str(value))
        if hasattr(self.channel, "send"):
            result = await self.channel.send(message=message, subject=subject)
        elif callable(self.channel):
            result = await self.channel(message=message, subject=subject)
        else:
            raise TypeError(f"Channel {type(self.channel)} is not callable or does not have 'send'")
        context.set(f"{self.name}_result", result)
        return result

    async def compensate(self, context: Any) -> None:
        context.logger.info(f"Compensating NotifyStep: {self.name} (no-op)")
