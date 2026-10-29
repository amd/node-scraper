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
import json
from datetime import datetime, timezone
from typing import Any, NamedTuple, Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish.redfish_clear_log import (
    _parse_clear_endpoint,
    clear_redfish_logs,
)
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemInteractionLevel,
)
from nodescraper.models import TaskResult

from .collector_args import RedfishEventLogCollectorArgs
from .event_log_data import EventLogEntry, RedfishEventLogDataModel, parse_created

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


class _EntriesRead(NamedTuple):
    members: list[dict[str, Any]]
    reported_count: int
    error: Optional[str]
    complete: bool


def _member_key(member: dict[str, Any]) -> str:
    key = member.get("@odata.id") or member.get("Id")
    return str(key) if key else json.dumps(member, sort_keys=True, default=str)


def _reported_count(data: dict[str, Any]) -> int:
    try:
        return int(data.get("Members@odata.count") or 0)
    except (TypeError, ValueError):
        return 0


class RedfishEventLogCollector(
    RedfishDataCollector[RedfishEventLogDataModel, RedfishEventLogCollectorArgs]
):
    """Reads every entry from a Redfish LogService's Entries collection."""

    DATA_MODEL = RedfishEventLogDataModel

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Redfish GET of <collection_args.log_service_path>/Entries, paged with $skip until "
        "Members@odata.count is reached; each page is saved as an artifact.",
        "Entries are sorted newest first by Created; collection_args.max_entries keeps only the newest N.",
        "Optional LogService.ClearLog after collection (collection_args.clear_logs_after_collection).",
    )

    def collect_data(
        self, args: Optional[RedfishEventLogCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishEventLogDataModel]]:
        """Read the LogService entries and return them newest first."""
        if args is None:
            args = RedfishEventLogCollectorArgs()
        entries_path = f"{args.log_service_path.rstrip('/')}/Entries"

        read = self._read_entries(entries_path, args.max_pages)
        if read.error is not None:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Could not read {entries_path}: {read.error}",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = f"EventLog: could not read {entries_path}"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        entries = sorted(
            (EventLogEntry.from_redfish(m) for m in read.members),
            key=lambda e: parse_created(e.created) or _OLDEST,
            reverse=True,
        )
        if args.max_entries:
            entries = entries[: args.max_entries]
        total = read.reported_count or len(read.members)

        self.result.message = f"EventLog: {len(entries)} of {total} entries from {entries_path}"
        self.result.status = ExecutionStatus.OK
        if not read.complete:
            self.result.status = ExecutionStatus.WARNING
            self.result.message += f" (read {len(read.members)}; pagination stopped early)"

        if args.clear_logs_after_collection:
            if self.system_interaction_level >= SystemInteractionLevel.INTERACTIVE:
                self._clear_log_service(args.log_service_path)
            else:
                self.logger.debug(
                    "Skipping log clear: system_interaction_level is %s (requires INTERACTIVE)",
                    self.system_interaction_level.name,
                )

        return self.result, RedfishEventLogDataModel(
            log_service_path=args.log_service_path,
            total_count=total,
            entries=entries,
        )

    def _read_entries(self, entries_path: str, max_pages: int) -> _EntriesRead:
        """Page through an Entries collection with $skip.

        $skip is used instead of Members@odata.nextLink because some services return the same
        nextLink on every page, which never terminates.

        Args:
            entries_path: Redfish path of the Entries collection.
            max_pages: Maximum number of pages to request.

        Returns:
            _EntriesRead: Members read, reported count, first-page error (if any), and whether
            every reported entry was read.
        """
        members: list[dict[str, Any]] = []
        seen: set[str] = set()
        reported = 0
        skip = 0
        for page in range(max_pages):
            path = entries_path if skip == 0 else f"{entries_path}?$skip={skip}"
            res = self._run_redfish_get(path)
            if not res.success or res.data is None:
                if page == 0:
                    return _EntriesRead([], 0, res.error or f"HTTP {res.status_code}", False)
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"EventLog page {path} failed: {res.error or res.status_code}",
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                return _EntriesRead(members, reported, None, False)

            if page == 0:
                reported = _reported_count(res.data)
            page_members = [m for m in res.data.get("Members") or [] if isinstance(m, dict)]
            new = [m for m in page_members if _member_key(m) not in seen]
            seen.update(_member_key(m) for m in new)
            members.extend(new)
            skip += len(page_members)

            if not new:
                complete = not reported or len(members) >= reported
                if not complete:
                    self._log_event(
                        category=EventCategory.RUNTIME,
                        description=(
                            f"EventLog {entries_path}: page at $skip={skip - len(page_members)} "
                            f"returned no new entries ({len(members)} of {reported} read)"
                        ),
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                return _EntriesRead(members, reported, None, complete)
            if reported and len(members) >= reported:
                return _EntriesRead(members, reported, None, True)
            if not reported and "Members@odata.nextLink" not in res.data:
                return _EntriesRead(members, reported, None, True)

        self._log_event(
            category=EventCategory.RUNTIME,
            description=(
                f"EventLog {entries_path}: stopped after max_pages={max_pages} "
                f"({len(members)} of {reported or '?'} read)"
            ),
            priority=EventPriority.WARNING,
            console_log=True,
        )
        return _EntriesRead(members, reported, None, False)

    def _clear_log_service(self, log_service_path: str) -> None:
        """POST LogService.ClearLog to the log service if it advertises the action.

        Args:
            log_service_path: Redfish path to the LogService.
        """
        svc_res = self._run_redfish_get(log_service_path, log_artifact=False)
        if not svc_res.success or not svc_res.data:
            self.logger.debug("Skipping log clear: could not GET log service %s", log_service_path)
            return
        endpoint = _parse_clear_endpoint(svc_res.data)
        if endpoint is None:
            self.logger.debug("LogService %s does not advertise ClearLog action", log_service_path)
            return
        clear_results = clear_redfish_logs(self.connection, [endpoint], self.logger)
        if clear_results and clear_results[0].success:
            self.result.message += "; cleared log store"
        elif clear_results:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"Failed to clear log store {endpoint.path}: {clear_results[0].error}",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            if self.result.status == ExecutionStatus.OK:
                self.result.status = ExecutionStatus.WARNING
                self.result.message += "; log clear failed"
