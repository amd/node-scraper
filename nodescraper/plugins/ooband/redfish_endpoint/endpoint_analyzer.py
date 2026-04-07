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
from typing import Any, Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import ConstraintKey, RedfishConstraint, RedfishEndpointAnalyzerArgs
from .endpoint_data import RedfishEndpointDataModel


def _get_by_path(obj: Any, path: str) -> Any:
    """Get a value from a nested dict/list."""
    if not path.strip():
        return obj
    current: Any = obj
    for segment in path.strip().split("/"):
        if not segment:
            continue
        if current is None:
            return None
        if isinstance(current, list):
            try:
                idx = int(segment)
                current = current[idx] if 0 <= idx < len(current) else None
            except ValueError:
                return None
        elif isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current


def _check_constraint(actual: Any, constraint: RedfishConstraint) -> tuple[bool, str]:
    """Compare actual value to constraint."""
    if isinstance(constraint, dict):
        if ConstraintKey.EQ in constraint:
            ok = actual == constraint[ConstraintKey.EQ]
            return ok, f"expected eq {constraint[ConstraintKey.EQ]}, got {actual!r}"
        if ConstraintKey.MIN in constraint or ConstraintKey.MAX in constraint:
            try:
                val = float(actual) if actual is not None else None
                if val is None:
                    return False, f"expected numeric, got {actual!r}"
                if ConstraintKey.MIN in constraint and val < constraint[ConstraintKey.MIN]:
                    return False, f"value {val} below min {constraint[ConstraintKey.MIN]}"
                if ConstraintKey.MAX in constraint and val > constraint[ConstraintKey.MAX]:
                    return False, f"value {val} above max {constraint[ConstraintKey.MAX]}"
                return True, ""
            except (TypeError, ValueError):
                return False, f"expected numeric, got {actual!r}"
        if ConstraintKey.ANY_OF in constraint:
            allowed = constraint[ConstraintKey.ANY_OF]
            if not isinstance(allowed, list):
                return False, "anyOf must be a list"
            ok = actual in allowed
            return ok, f"expected any of {allowed}, got {actual!r}"
    ok = actual == constraint
    return ok, f"expected {constraint!r}, got {actual!r}"


class RedfishEndpointAnalyzer(DataAnalyzer[RedfishEndpointDataModel, RedfishEndpointAnalyzerArgs]):
    """Checks Redfish endpoint responses against configured thresholds and key/value rules."""

    DATA_MODEL = RedfishEndpointDataModel

    def analyze_data(
        self,
        data: RedfishEndpointDataModel,
        args: Optional[RedfishEndpointAnalyzerArgs] = None,
    ) -> TaskResult:
        """Evaluate each configured check against the collected Redfish responses."""
        if not args or not args.checks:
            self.result.status = ExecutionStatus.OK
            self.result.message = "No checks configured"
            return self.result

        failed: list[dict[str, Any]] = []
        for uri, path_constraints in args.checks.items():
            if uri == "*":
                bodies = list(data.responses.values())
            else:
                body = data.responses.get(uri)
                bodies = [body] if body is not None else []
            if not bodies:
                if uri != "*":
                    failed.append(
                        {"uri": uri, "path": None, "reason": "URI not in collected responses"}
                    )
                continue
            for resp in bodies:
                for path, constraint in path_constraints.items():
                    actual = _get_by_path(resp, path)
                    ok, msg = _check_constraint(actual, constraint)
                    if not ok:
                        failed.append(
                            {
                                "uri": uri,
                                "path": path,
                                "expected": constraint,
                                "actual": actual,
                                "reason": msg,
                            }
                        )

        if failed:
            description = f"Redfish endpoint checks failed: {len(failed)} failure(s)"
            self._log_event(
                category=EventCategory.TELEMETRY,
                description=description,
                data={"failures": failed},
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.ERROR
            self.result.message = f"{len(failed)} check(s) failed"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = "All Redfish endpoint checks passed"
        return self.result
