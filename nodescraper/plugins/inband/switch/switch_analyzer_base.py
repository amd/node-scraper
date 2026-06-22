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

import datetime
import logging
import re
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import DataModel, TaskResult
from nodescraper.utils import get_exception_traceback

TSwitchData = TypeVar("TSwitchData", bound=DataModel)


def _unwrap_optional(annotation: Any) -> Any:
    """Strip a single ``None`` arm from ``Optional[X]`` / ``X | None``"""

    args = get_args(annotation)
    if not args:
        return annotation
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == 1 and len(non_none) < len(args):
        return non_none[0]
    return annotation


@lru_cache(maxsize=None)
def _classify_port_submodel_fields(
    port_cls: Type[BaseModel],
) -> tuple[tuple[tuple[str, Type[BaseModel]], ...], tuple[tuple[str, Type[BaseModel]], ...]]:
    """Inspect a per-port pydantic model and split its sub-model fields"""

    scalars: list[tuple[str, Type[BaseModel]]] = []
    lists: list[tuple[str, Type[BaseModel]]] = []

    for name, field in port_cls.model_fields.items():
        inner = _unwrap_optional(field.annotation)

        if isinstance(inner, type) and issubclass(inner, BaseModel):
            scalars.append((name, inner))
            continue

        origin = get_origin(inner)
        if origin in (list, tuple):
            elem_args = get_args(inner)
            if elem_args:
                elem = _unwrap_optional(elem_args[0])
                if isinstance(elem, type) and issubclass(elem, BaseModel):
                    lists.append((name, elem))

    return tuple(scalars), tuple(lists)


def _model_is_analyzed(model_cls: Type[BaseModel]) -> bool:
    """Return True if ``model_cls`` declares any error/warning fields"""

    return bool(
        getattr(model_cls, "error_fields", None) or getattr(model_cls, "warning_fields", None)
    )


def _values_match(actual: Any, expected: Any) -> bool:
    """Compare an actual model value to an expected value."""

    if isinstance(expected, str) and expected == "NOT_NULL":
        if actual is None:
            return False
        return str(actual) != ""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(actual) == bool(expected)
    return str(actual) == str(expected)


class SwitchAnalyzerBase(Generic[TSwitchData]):
    """Shared scaffolding for vendor-specific switch analyzers.

    A mixin that walks the vendor data model and flags sub-models whose
    ``error_fields`` / ``warning_fields`` values mismatch.
    Subclasses set :attr:`VENDOR_NAME`, :attr:`DATA_MODEL`,
    :attr:`PORT_NAME_RE`, :attr:`PORT_FORMAT_HINT` and may override
    :meth:`_walk_system` for non-port checks.
    """

    VENDOR_NAME: ClassVar[str]
    DATA_MODEL: Type[DataModel]
    PORT_NAME_RE: ClassVar[re.Pattern]
    PORT_FORMAT_HINT: ClassVar[str] = "expected canonical port form"

    if TYPE_CHECKING:
        # These attributes/methods are provided by ``DataAnalyzer`` (via
        # ``Task``) on the concrete vendor analyzer that mixes this class in.
        result: TaskResult
        logger: logging.Logger

        def _log_event(
            self,
            category: Union[EventCategory, str],
            description: str,
            priority: EventPriority,
            data: Optional[dict] = None,
            timestamp: Optional[datetime.datetime] = None,
            console_log: bool = False,
        ) -> None: ...

    def analyze_data(
        self,
        data: TSwitchData,
        args: Optional[BaseModel] = None,
    ) -> TaskResult:
        """Analyze a single vendor's switch data model"""

        ports = getattr(args, "analysis_ports", None) if args is not None else None

        try:
            allowed_ports = self._parse_ports_kwarg(ports)
        except (TypeError, ValueError) as exc:
            self.result.message = f"Invalid 'ports' filter: {exc}"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        try:
            error_state = self._run_checks(data, allowed_ports)
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Unhandled error while analyzing {self.VENDOR_NAME} data",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = f"{self.VENDOR_NAME} analysis failed with an unhandled error"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result

        if error_state:
            self.result.message = f"{self.VENDOR_NAME} errors or warnings detected"
        else:
            self.result.message = f"No {self.VENDOR_NAME} errors or warnings detected"

        return self.result

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    def _walk_system(self, switch_data: TSwitchData) -> list[dict[str, Any]]:
        """Return findings for vendor-specific top-level (non-port) sections"""

        return []

    # ------------------------------------------------------------------
    # Common machinery
    # ------------------------------------------------------------------

    def _normalize_port(self, name: str) -> Optional[str]:
        """Return ``name`` as a canonical port key, else ``None``"""

        match = self.PORT_NAME_RE.match(name.strip())
        if not match:
            return None
        # Vendor regexes either expose a single capture group with the
        # whole canonical key (slash-joined) or two groups (M, S).
        groups = match.groups()
        if len(groups) == 1:
            return groups[0]
        if len(groups) == 2 and groups[1] is not None:
            return f"{groups[0]}/{groups[1]}"
        return groups[0]

    def _parse_ports_kwarg(self, ports: Any) -> Optional[set[str]]:
        """Parse the ``ports`` filter into a set of canonical port keys"""

        if ports is None:
            return None

        if not isinstance(ports, list):
            raise TypeError(f"Port filter must be a list of strings, got {ports!r}")

        allowed: set[str] = set()
        for token in ports:
            if not isinstance(token, str):
                raise TypeError(f"Port filter entries must be strings, got {token!r}")
            normalized = self._normalize_port(token)
            if normalized is None:
                raise ValueError(f"Invalid port identifier {token!r}; {self.PORT_FORMAT_HINT}")
            allowed.add(normalized)

        return allowed or None

    def _run_checks(
        self,
        switch_data: TSwitchData,
        allowed_ports: Optional[set[str]],
    ) -> bool:
        """Execute system- and per-port-level checks"""

        findings: list[dict[str, Any]] = list(self._walk_system(switch_data))

        analyzed_ports: list[str] = []
        skipped_ports: list[str] = []
        ports_map = getattr(switch_data, "port", None) or {}
        for port_name, port_data in ports_map.items():
            if port_data is None:
                continue
            if allowed_ports is not None:
                normalized = self._normalize_port(port_name)
                if normalized is None or normalized not in allowed_ports:
                    skipped_ports.append(port_name)
                    continue
            analyzed_ports.append(port_name)
            findings.extend(self._check_port(port_name, port_data))

        if allowed_ports is not None:
            self.logger.info(
                "%s port filter applied: analyzed=%s skipped=%d",
                self.VENDOR_NAME,
                analyzed_ports,
                len(skipped_ports),
            )
            unmatched = allowed_ports - {self._normalize_port(p) or "" for p in analyzed_ports}
            if unmatched:
                self.logger.warning(
                    "%s port filter had no matching data for: %s",
                    self.VENDOR_NAME,
                    sorted(unmatched),
                )

        self._emit_grouped_findings(findings)
        return bool(findings)

    def _emit_grouped_findings(self, findings: list[dict[str, Any]]) -> None:
        """Emit at most one event per (location, priority) group"""

        # Preserve discovery order of locations and priorities.
        grouped: dict[tuple[str, EventPriority], list[dict[str, Any]]] = {}
        for finding in findings:
            port = finding["context"].get("port")
            location = port if port else "system"
            key = (location, finding["priority"])
            grouped.setdefault(key, []).append(finding)

        for (location, priority), items in grouped.items():
            kind = "warnings" if priority == EventPriority.WARNING else "errors"
            mismatches = ", ".join(self._format_mismatch(item) for item in items)
            self._log_event(
                category=EventCategory.NETWORK,
                description=(f"{self.VENDOR_NAME} {kind} detected on {location}: {mismatches}"),
                data={
                    "location": location,
                    "mismatches": [
                        {
                            **dict(item["context"]),
                            "field": item["field"],
                            "actual": item["actual"],
                            "expected": item.get("expected"),
                            **({"missing": True} if item.get("missing") else {}),
                        }
                        for item in items
                    ],
                },
                priority=priority,
                console_log=True,
            )

    @staticmethod
    def _format_mismatch(item: dict[str, Any]) -> str:
        """Render a single finding for the event description"""

        section = item["context"].get("section")
        prefix = f"{section}." if section else ""
        if item.get("missing"):
            return f"{item['field']} (not collected)"
        return f"{prefix}{item['field']}={item['actual']!r}"

    def _check_port(self, port_name: str, port_data: BaseModel) -> list[dict[str, Any]]:
        """Check every sub-model of a single port for errors/warnings.

        Analyzed sub-models that were not collected produce a missing-data
        warning.
        """

        findings: list[dict[str, Any]] = []

        scalar_attrs, list_attrs = _classify_port_submodel_fields(type(port_data))

        for attr, model_cls in scalar_attrs:
            model = getattr(port_data, attr, None)
            if model is None:
                if _model_is_analyzed(model_cls):
                    findings.append(self._missing_submodel_finding(port_name, attr, model_cls))
                continue
            findings.extend(
                self._check_model(
                    model,
                    context={"port": port_name, "section": attr},
                )
            )

        for attr, elem_cls in list_attrs:
            items = getattr(port_data, attr, None)
            if items is None:
                if _model_is_analyzed(elem_cls):
                    findings.append(self._missing_submodel_finding(port_name, attr, elem_cls))
                continue
            for idx, item in enumerate(items):
                if item is None:
                    continue
                findings.extend(
                    self._check_model(
                        item,
                        context={"port": port_name, "section": attr, "index": idx},
                    )
                )

        return findings

    def _missing_submodel_finding(
        self, port_name: str, attr: str, model_cls: Type[BaseModel]
    ) -> dict[str, Any]:
        """Build a warning finding for an analyzed sub-model that is absent"""

        return {
            "priority": EventPriority.WARNING,
            "field": attr,
            "actual": None,
            "model": model_cls.__name__,
            "missing": True,
            "context": {"port": port_name, "section": attr},
        }

    def _check_model(self, model: BaseModel, context: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Check a single pydantic model against its error/warning field dicts"""

        findings: list[dict[str, Any]] = []

        for fields, priority in (
            (getattr(type(model), "error_fields", None), EventPriority.ERROR),
            (getattr(type(model), "warning_fields", None), EventPriority.WARNING),
        ):
            if not fields:
                continue
            findings.extend(self._check_fields(model, fields, priority, context))

        return findings

    def _check_fields(
        self,
        model: BaseModel,
        fields: Union[Mapping[str, Any], Iterable[str]],
        priority: EventPriority,
        context: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Compare each named field on ``model`` to its expected value"""

        findings: list[dict[str, Any]] = []

        # Support either a dict[name -> expected] or a plain iterable of names
        # (where the implicit expected value is 0 / "0").
        iterator: Iterable[tuple[str, Any]]
        if isinstance(fields, Mapping):
            iterator = fields.items()
        else:
            iterator = ((name, "0") for name in fields)

        for field_name, expected in iterator:
            if not hasattr(model, field_name):
                continue
            actual = getattr(model, field_name)
            if actual is None and not (isinstance(expected, str) and expected == "NOT_NULL"):
                continue
            if _values_match(actual, expected):
                continue

            findings.append(
                {
                    "priority": priority,
                    "field": field_name,
                    "actual": actual,
                    "expected": expected,
                    "model": type(model).__name__,
                    "context": dict(context),
                }
            )

        return findings
