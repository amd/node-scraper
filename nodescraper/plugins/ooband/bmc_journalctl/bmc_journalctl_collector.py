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
"""BMC journal collector that runs journalctl on the BMC console over SSH."""

from __future__ import annotations

import json
import re
import shlex
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .bmc_journalctl_collector_args import JournalctlCollectorArgs, JournalctlMode
from .bmc_journalctl_data import JournalctlData, JournalctlEntry

JOURNALCTL_TIMEOUT = 420
BMC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S UTC"
OUTPUT_FIELDS = "MESSAGE,PRIORITY,SYSLOG_IDENTIFIER,_SYSTEMD_UNIT,_PID,_HOSTNAME,_TRANSPORT"
JOURNALCTL_BASE = (
    f"SYSTEMD_COLORS=0 journalctl --no-pager -q -o json --output-fields={OUTPUT_FIELDS}"
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
BOOT_ID_PATTERN = re.compile(r"\b([0-9a-f]{32})\b")


class JournalctlCollector(InBandDataCollector[JournalctlData, JournalctlCollectorArgs]):
    """Collect BMC journal entries by running journalctl over BMC SSH."""

    DATA_MODEL = JournalctlData
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX, OSFamily.UNKNOWN}

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "Runs journalctl on the BMC or AMC over SSH and parses the JSON output.",
        "Supports modes: all, last_lines, first_lines, line_range, since, until, time_range, unit, boot.",
        "The default priority is unset, so debug entries are collected.",
        "A non-zero journalctl exit code fails the collection.",
        "Entries are capped at collection_args.max_entries. The cap keeps the newest entries, except first_lines and line_range.",
    )

    def collect_data(
        self, args: Optional[JournalctlCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[JournalctlData]]:
        if args is None:
            args = JournalctlCollectorArgs()

        self._collected_command = ""
        self._truncated = False

        dispatch = {
            JournalctlMode.ALL: lambda: self._collect_all(args),
            JournalctlMode.LAST_LINES: lambda: self._collect_last_lines(args.line_count, args),
            JournalctlMode.FIRST_LINES: lambda: self._collect_first_lines(args.line_count, args),
            JournalctlMode.LINE_RANGE: lambda: self._collect_line_range(
                args.require(args.line_start, "line_start"),
                args.require(args.line_end, "line_end"),
                args,
            ),
            JournalctlMode.SINCE: lambda: self._collect_since(
                args.require(args.collect_since, "collect_since"), args
            ),
            JournalctlMode.UNTIL: lambda: self._collect_until(
                args.require(args.collect_until, "collect_until"), args
            ),
            JournalctlMode.TIME_RANGE: lambda: self._collect_time_range(
                args.require(args.collect_since, "collect_since"),
                args.require(args.collect_until, "collect_until"),
                args,
            ),
            JournalctlMode.UNIT: lambda: self._collect_from_units(
                args.require(args.unit, "unit"), args
            ),
            JournalctlMode.BOOT: lambda: self._collect_from_boot(args.boots, args),
        }

        entries = dispatch[args.mode]()
        if entries is None:
            return self.result, None

        return self.result, JournalctlData(
            entries=entries,
            mode=args.mode.value,
            command=self._collected_command,
            truncated=self._truncated,
        )

    def _collect_all(self, args: JournalctlCollectorArgs) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl([], args)

    def _collect_last_lines(
        self, count: int, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl([f"-n {min(count, args.max_entries)}"], args)

    def _collect_first_lines(
        self, count: int, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl(
            [],
            args,
            pipeline=[f"head -n {min(count, args.max_entries)}"],
            newest=False,
        )

    def _collect_line_range(
        self, start: int, end: int, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl(
            [],
            args,
            pipeline=[f"sed -n '{start},{end}p;{end}q'"],
            newest=False,
        )

    def _collect_since(
        self, start: str, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl([f"--since {shlex.quote(start)}"], args)

    def _collect_until(
        self, end: str, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl([f"--until {shlex.quote(end)}"], args)

    def _collect_time_range(
        self, start: str, end: str, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        return self._run_journalctl(
            [f"--since {shlex.quote(start)}", f"--until {shlex.quote(end)}"], args
        )

    def _collect_from_units(
        self, units: list[str], args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        entries: list[JournalctlEntry] = []
        commands: list[str] = []
        count = min(args.line_count, args.max_entries)
        for unit in units:
            collected = self._run_journalctl([f"-u {shlex.quote(unit)}", f"-n {count}"], args)
            if collected is None:
                return None
            entries.extend(collected)
            commands.append(self._collected_command)
        self._collected_command = " ; ".join(commands)
        if len(entries) > args.max_entries:
            entries.sort(key=self._entry_sort_key)
            entries = entries[-args.max_entries :]
            self._mark_truncated(args)
        return entries

    @staticmethod
    def _entry_sort_key(entry: JournalctlEntry) -> tuple[int, float]:
        """Order undated entries before dated ones, then by time.

        Args:
            entry (JournalctlEntry): journal record being ordered

        Returns:
            tuple[int, float]: sort key, with dated entries after undated ones
        """
        if entry.timestamp is None:
            return (0, 0.0)
        return (1, entry.timestamp.timestamp())

    def _collect_from_boot(
        self, boots: int, args: JournalctlCollectorArgs
    ) -> Optional[list[JournalctlEntry]]:
        boot_ids = self._list_boot_ids()
        if boot_ids is None:
            return None
        if not boot_ids:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No boot IDs reported by 'journalctl --list-boots'",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return None

        wanted = boot_ids[-boots:]
        if len(wanted) < boots:
            self._log_event(
                category=EventCategory.PLATFORM,
                description=(
                    f"Requested {boots} boots but the BMC journal retains "
                    f"{len(wanted)}; collecting what is available"
                ),
                priority=EventPriority.INFO,
                data={"available_boots": len(boot_ids)},
            )

        boot_collections: list[tuple[list[JournalctlEntry], str]] = []
        collected_count = 0
        for boot_id in reversed(wanted):
            remaining = args.max_entries - collected_count
            if remaining <= 0:
                self._mark_truncated(args)
                break
            boot_args = args.model_copy(update={"max_entries": remaining})
            collected = self._run_journalctl([f"-b {boot_id}"], boot_args)
            if collected is None:
                return None
            if len(collected) > remaining:
                collected = collected[-remaining:]
                self._mark_truncated(args)
            boot_collections.append((collected, self._collected_command))
            collected_count += len(collected)
            if collected_count >= args.max_entries:
                break
        chronological_collections = list(reversed(boot_collections))
        self._collected_command = " ; ".join(command for _, command in chronological_collections)
        return [entry for entries, _ in chronological_collections for entry in entries]

    def _list_boot_ids(self) -> Optional[list[str]]:
        raw = self._run_bmc_command("journalctl --no-pager --list-boots")
        if raw is None:
            return None
        return [
            match.group(1)
            for match in (BOOT_ID_PATTERN.search(line) for line in raw.splitlines())
            if match
        ]

    def _run_journalctl(
        self,
        flags: list[str],
        args: JournalctlCollectorArgs,
        pipeline: Optional[list[str]] = None,
        newest: bool = True,
    ) -> Optional[list[JournalctlEntry]]:
        command = self._build_command(flags, args, pipeline, newest)
        self._collected_command = command
        raw = self._run_bmc_command(command, max_entries=self._sigpipe_threshold(args))
        if raw is None:
            return None

        entries, skipped = self._parse_entries(raw)
        if skipped:
            self._log_event(
                category=EventCategory.PLATFORM,
                description=f"Skipped {skipped} non-JSON line(s) in journalctl output",
                priority=EventPriority.WARNING,
                data={"skipped_lines": skipped, "command": command},
            )
        if len(raw.splitlines()) >= args.max_entries:
            self._mark_truncated(args)

        self.result.status = ExecutionStatus.OK
        return entries

    def _mark_truncated(self, args: JournalctlCollectorArgs) -> None:
        """Record that the entry ceiling dropped part of the journal.

        Args:
            args (JournalctlCollectorArgs): collection arguments carrying max_entries

        Returns:
            None
        """
        if self._truncated:
            return
        self._truncated = True
        self._log_event(
            category=EventCategory.PLATFORM,
            description=(
                f"Collection hit the {args.max_entries} entry ceiling; "
                "the journal holds more entries than were collected"
            ),
            priority=EventPriority.WARNING,
            console_log=True,
        )

    @staticmethod
    def _build_command(
        flags: list[str],
        args: JournalctlCollectorArgs,
        pipeline: Optional[list[str]] = None,
        newest: bool = True,
    ) -> str:
        parts = [JOURNALCTL_BASE]
        if args.priority:
            parts.append(f"-p {shlex.quote(args.priority)}")
        parts.extend(flags)
        cap = f"tail -n {args.max_entries}" if newest else f"head -n {args.max_entries}"
        stages = [" ".join(parts), *(pipeline or []), cap]
        return "set -o pipefail; " + " | ".join(stages)

    @staticmethod
    def _sigpipe_threshold(args: JournalctlCollectorArgs) -> int:
        """Return the line count that makes exit 141 an intentional pipe close.

        Args:
            args (JournalctlCollectorArgs): collection arguments

        Returns:
            int: output size at which SIGPIPE is expected
        """
        threshold = args.max_entries
        if args.mode == JournalctlMode.FIRST_LINES:
            return min(args.line_count, threshold)
        if args.mode == JournalctlMode.LINE_RANGE:
            start = args.require(args.line_start, "line_start")
            end = args.require(args.line_end, "line_end")
            return min(end - start + 1, threshold)
        return threshold

    def _run_bmc_command(self, command: str, max_entries: Optional[int] = None) -> Optional[str]:
        try:
            result = self.connection.run_command(command, timeout=JOURNALCTL_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            self._log_event(
                category=EventCategory.PLATFORM,
                description="Failed to run journalctl on the target console",
                priority=EventPriority.WARNING,
                data={"error": str(exc), "command": command},
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return None
        if result.exit_code != 0 and not (
            result.exit_code == 141
            and max_entries is not None
            and len(result.stdout.splitlines()) >= max_entries
        ):
            self._log_event(
                category=EventCategory.PLATFORM,
                description="journalctl failed on the target console",
                priority=EventPriority.WARNING,
                data={
                    "exit_code": result.exit_code,
                    "stderr": result.stderr,
                    "command": command,
                },
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return None
        return result.stdout

    @staticmethod
    def _parse_entries(raw: str) -> tuple[list[JournalctlEntry], int]:
        entries: list[JournalctlEntry] = []
        skipped = 0
        for line in ANSI_ESCAPE.sub("", raw).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if not isinstance(record, dict):
                skipped += 1
                continue
            entries.append(JournalctlEntry(**record))
        return entries, skipped
