###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import logging
from typing import Any, Optional, Union

from nodescraper.base import InBandDataPlugin
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemLocation,
)
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models import CollectorArgs, Event, SystemInfo, TaskResult

from .collector_args import RegisterDecodeCollectorArgs
from .register_decode_analyzer import RegisterDecodeAnalyzer
from .register_decode_collector import RegisterDecodeCollector
from .register_decode_data import RegisterDecodeDataModel
from .register_tool import discover_register_tool, tool_rows


class RegisterDecodePlugin(
    InBandDataPlugin[RegisterDecodeDataModel, RegisterDecodeCollectorArgs, None]
):
    """Expose register-tool steps for an installed entry point."""

    DATA_MODEL = RegisterDecodeDataModel
    COLLECTOR = RegisterDecodeCollector
    ANALYZER = RegisterDecodeAnalyzer
    COLLECTOR_ARGS = RegisterDecodeCollectorArgs

    def __init__(
        self,
        system_info: SystemInfo,
        tool_group: Optional[str] = None,
        tool_name: Optional[str] = None,
        **kwargs,
    ):
        """Store the register tool selected for this plugin instance.

        Args:
            system_info: System this plugin runs against.
            tool_group: Entry-point group used to discover the register tool.
            tool_name: Entry-point name. Required when more than one tool is installed.
            kwargs: Arguments forwarded to the plugin base.
        """
        self.tool_group = tool_group
        self.tool_name = tool_name
        self._register_tool = None
        self.result = TaskResult(task=self.__class__.__name__, parent=self.__class__.__name__)
        super().__init__(system_info, **kwargs)

    def health_check(self) -> TaskResult:
        """Check that the register tool can read registers.

        Returns:
            OK when the tool status is 0. NOT_RAN when the tool has no health check.
        """
        self._begin("health_check")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        try:
            method = self._optional_method("health_check")
            if method is None:
                return self.result
            status = int(method())
        except Exception as exc:
            return self._fail(f"Register health check failed: {exc}")
        if status != 0:
            return self._fail(f"Register tool health check failed with status {status}")
        self.result.status = ExecutionStatus.OK
        self.result.message = "Register tool health check passed"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            priority=EventPriority.INFO,
        )
        return self.result

    def collect(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        system_interaction_level: Optional[
            Union[SystemInteractionLevel, str]
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        collection_args: Optional[Union[CollectorArgs, dict]] = None,
    ) -> TaskResult:
        """Read registers.

        Args:
            max_event_priority_level: Priority limit for events.
            system_interaction_level: System interaction level.
            preserve_connection: Leave the connection open after collection.
            collection_args: Scan options. tool_group comes from the plugin when omitted.

        Returns:
            Task result for the register read.
        """
        return super().collect(
            max_event_priority_level=max_event_priority_level,
            system_interaction_level=system_interaction_level,
            preserve_connection=preserve_connection,
            collection_args=self._apply_tool_selection(collection_args),
        )

    def decode(self) -> TaskResult:
        """Decode the register records stored on this plugin.

        Returns:
            OK with decoded records, or NOT_RAN when the tool has no decode method.
        """
        self._begin("decode")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        if self.data is None:
            return self._fail("No register records to decode")
        try:
            method = self._optional_method("decode_records")
            if method is None:
                return self.result
            records = list(self.data.records)
            convert = getattr(self._tool(), "record_from_row", None)
            if callable(convert):
                records = [convert(row) for row in records]
            self.data.decoded_records = tool_rows(method(records))
        except Exception as exc:
            return self._fail(f"Register decode failed: {exc}")
        count = len(self.data.decoded_records)
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Decoded {count} register record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"records": self.data.decoded_records},
            priority=EventPriority.INFO,
        )
        return self.result

    def _apply_tool_selection(
        self, collection_args: Optional[Union[CollectorArgs, dict]]
    ) -> Optional[RegisterDecodeCollectorArgs]:
        """Copy the plugin tool selection into collection args when they omit it.

        Args:
            collection_args: Scan options passed to collect.

        Returns:
            Collection args that include the plugin tool selection.
        """
        if isinstance(collection_args, CollectorArgs):
            raw = collection_args.model_dump()
        else:
            raw = dict(collection_args or {})
        if raw.get("tool_group") is None and self.tool_group is not None:
            raw["tool_group"] = self.tool_group
        if raw.get("tool_name") is None and self.tool_name is not None:
            raw["tool_name"] = self.tool_name
        if not raw:
            return None
        validated = self._collector_args_cls().model_validate(raw)
        if not isinstance(validated, RegisterDecodeCollectorArgs):
            raise TypeError("collector args are not register decode args")
        return validated

    def _collector_args_cls(self) -> type[CollectorArgs]:
        """Return the collector args model for this plugin.

        Returns:
            Collector args class.
        """
        args_cls = self.COLLECTOR_ARGS
        if isinstance(args_cls, dict):
            args_cls = next(iter(args_cls.values()))
        if isinstance(args_cls, type):
            return args_cls
        return RegisterDecodeCollectorArgs

    def _optional_method(self, name: str) -> Optional[Any]:
        """Return a tool method, or record NOT_RAN when the tool does not provide it.

        Args:
            name: Method name on the register tool.

        Returns:
            Bound method, or None when the tool does not provide it.
        """
        method = getattr(self._tool(), name, None)
        if callable(method):
            return method
        self.result.status = ExecutionStatus.NOT_RAN
        self.result.message = f"register tool does not provide {name}"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            priority=EventPriority.INFO,
            console_log=True,
        )
        return None

    def _tool(self) -> Any:
        """Return the register tool discovered for this plugin.

        Returns:
            Cached register tool.
        """
        if self._register_tool is None:
            self._register_tool = discover_register_tool(name=self.tool_name, group=self.tool_group)
        return self._register_tool

    def _begin(self, task: str) -> TaskResult:
        """Start a fresh task result for one plugin method.

        Args:
            task: Task name stored on the result.

        Returns:
            The new task result.
        """
        self.result = TaskResult(task=task, parent=self.__class__.__name__)
        return self.result

    def _remote_message(self) -> str:
        """Return the message used when a step runs on a remote system.

        Returns:
            Remote-system message.
        """
        return "Register operations are only supported on local"

    def _reject_remote(self) -> Optional[TaskResult]:
        """Reject the current method when the system is remote.

        Returns:
            NOT_RAN result for a remote system, or None when the system is local.
        """
        if self.system_info.location != SystemLocation.REMOTE:
            return None
        message = self._remote_message()
        self.result.status = ExecutionStatus.NOT_RAN
        self.result.message = message
        self._log_event(
            category=EventCategory.RAS,
            description=message,
            priority=EventPriority.INFO,
            console_log=True,
        )
        return self.result

    def _fail(self, message: str) -> TaskResult:
        """Record a method failure.

        Args:
            message: Failure text stored on the task result.

        Returns:
            The failed task result.
        """
        self.result.status = ExecutionStatus.ERROR
        self.result.message = message
        self._log_event(
            category=EventCategory.RAS,
            description=message,
            priority=EventPriority.ERROR,
            console_log=True,
        )
        return self.result

    def _log_event(
        self,
        category: Union[EventCategory, str],
        description: str,
        priority: EventPriority,
        data: Optional[dict] = None,
        console_log: bool = False,
    ) -> None:
        """Attach an event to the current task result.

        Args:
            category: Event category.
            description: Event text.
            priority: Event priority.
            data: Extra event data.
            console_log: Also write the description to the plugin logger.
        """
        category_value = category.value if isinstance(category, EventCategory) else category
        self.result.events.append(
            Event(
                reporter=self.event_reporter,
                category=category_value,
                description=description,
                priority=priority,
                data=data or {},
            )
        )
        if console_log:
            level = getattr(logging, priority.name, logging.INFO)
            self.logger.log(level, "%s", description)
