###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
import csv
from typing import ClassVar, Optional

from typing_extensions import override

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact, TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import DimmCollectorArgs
from .dimmdata import DimmDataModel, DimmInfo


class DimmCollector(InBandDataCollector[DimmDataModel, DimmCollectorArgs]):
    """Collect data on installed DIMMs"""

    DATA_MODEL: type[DimmDataModel] = DimmDataModel

    # Both platforms dump every field the firmware exposes and decode it here,
    # rather than filtering on the SUT, so that a shell quirk on any given host
    # cannot silently drop modules from the inventory.
    CMD_WINDOWS: ClassVar[str] = "wmic memorychip get /format:csv"
    CMD_DMIDECODE: ClassVar[str] = "dmidecode -q --type 17"
    CMD_DMIDECODE_FULL: ClassVar[str] = "dmidecode"

    # Section title of a DMI type 17 record, which is all that identifies one
    # under -q since that hides the handle lines.
    MEMORY_DEVICE: ClassVar[str] = "Memory Device"

    @override
    def collect_data(
        self,
        args: Optional[DimmCollectorArgs] = None,
    ) -> tuple[TaskResult, Optional[DimmDataModel]]:
        """Collect data on installed DIMMs"""
        if args is None:
            args = DimmCollectorArgs()

        if self.system_info.os_family == OSFamily.WINDOWS:
            records = self._collect_windows_records()
        else:
            if args.skip_sudo:
                self.result.message = "Skipping sudo plugin"
                self.result.status = ExecutionStatus.NOT_RAN
                return self.result, None

            records = self._collect_dmidecode_records()

        # Records for empty slots, and any the firmware reports too incompletely
        # to decode, come back as None and are dropped from the inventory.
        dimms = [dimm for dimm in map(DimmInfo.from_record, records) if dimm]

        if not dimms:
            self._log_event(
                category=EventCategory.IO,
                description="DIMM info not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "DIMM info not found"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        dimm_data = DimmDataModel(dimms=dimms)
        self._log_event(
            category=EventCategory.IO,
            description="Installed DIMM check",
            data=dimm_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"DIMM: {dimm_data}"

        return self.result, dimm_data

    def _collect_dmidecode_records(self) -> list[dict[str, str]]:
        """Dump the DMI tables and pull the memory device records out of them.

        A full dump is collected first and kept as an artifact, then the type 17
        records are read from a quiet, targeted dump. The full dump is used as a
        fallback when the targeted one fails, since it carries the same records.

        Returns:
            list[dict[str, str]]: one raw record per memory device slot.
        """
        full_dump = self._run_dmidecode(self.CMD_DMIDECODE_FULL)
        if full_dump:
            self.result.artifacts.append(
                TextFileArtifact(filename="dmidecode.txt", contents=full_dump)
            )
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Could not collect full dmidecode output",
                priority=EventPriority.WARNING,
            )

        dump = self._run_dmidecode(self.CMD_DMIDECODE) or full_dump
        if not dump:
            return []

        return self._parse_dmidecode(dump)

    def _run_dmidecode(self, command: str) -> Optional[str]:
        """Run a dmidecode command and return its output.

        Args:
            command (str): dmidecode command to run.

        Returns:
            Optional[str]: raw stdout, or None if the command produced none.
        """
        res = self._run_sut_cmd(command, sudo=True)

        # Hosts that already run as root often ship no sudo binary at all, so a
        # sudo specific failure is worth one retry without it.
        if res.exit_code != 0 and "sudo" in str(res.stderr).lower():
            res = self._run_sut_cmd(command, sudo=False)

        if res.exit_code != 0 or not res.stdout:
            self._log_cmd_error(res)
            return None

        return res.stdout

    def _collect_windows_records(self) -> list[dict[str, str]]:
        """Dump every Win32_PhysicalMemory property and split it into records.

        Returns:
            list[dict[str, str]]: one raw record per memory device slot.
        """
        res = self._run_sut_cmd(self.CMD_WINDOWS)
        if res.exit_code != 0 or not res.stdout:
            self._log_cmd_error(res)
            return []

        self.result.artifacts.append(
            TextFileArtifact(filename="memorychip.csv", contents=res.stdout)
        )

        return self._parse_wmic_csv(res.stdout)

    def _log_cmd_error(self, res: CommandArtifact) -> None:
        """Log a failed memory query without aborting the rest of the collection.

        Args:
            res (CommandArtifact): result of the failed command.
        """
        self._log_event(
            category=EventCategory.OS,
            description="Error checking dimms",
            data={
                "command": res.command,
                "exit_code": res.exit_code,
                "stderr": res.stderr,
            },
            priority=EventPriority.ERROR,
            console_log=True,
        )

    @classmethod
    def _parse_dmidecode(cls, dump: str) -> list[dict[str, str]]:
        """Split a raw dmidecode dump into its memory device records.

        Only DMI type 17 records are kept, and only their top level fields, so
        that the "Volatile Size", "Cache Size" and "Logical Size" fields nested
        under NVDIMM records are never mistaken for a module capacity.

        Args:
            dump (str): raw dmidecode output.

        Returns:
            list[dict[str, str]]: one raw record per memory device slot.
        """
        records: list[dict[str, str]] = []
        fields: Optional[dict[str, str]] = None

        for line in dump.splitlines():
            field = line.strip()
            if not field:
                # A blank line closes the current record.
                fields = None
            elif field.startswith("Handle "):
                # Without -q every record opens with a handle line naming its
                # DMI type, which is the most precise way to spot type 17.
                fields = None
                if "DMI type 17," in field:
                    fields = {}
                    records.append(fields)
            elif field == cls.MEMORY_DEVICE:
                # Under -q the handle lines are hidden, so the section title is
                # what opens the record.
                if fields is None:
                    fields = {}
                    records.append(fields)
            elif fields is not None:
                key, separator, value = field.partition(":")
                key = key.strip()
                # Nested fields repeat names such as "Size", so the first value
                # seen for a key wins.
                if separator and key not in fields:
                    fields[key] = value.strip()

        return records

    @staticmethod
    def _parse_wmic_csv(stdout: str) -> list[dict[str, str]]:
        """Split `wmic memorychip get /format:csv` output into records.

        wmic emits a header row naming each property followed by one row per
        module, so the header is used to key the fields and any property that a
        given Windows build does not report is simply absent from the record.

        Args:
            stdout (str): raw wmic output.

        Returns:
            list[dict[str, str]]: one raw record per memory device slot.
        """
        # wmic pads its output with blank lines that confuse the csv reader.
        rows = [line for line in stdout.splitlines() if line.strip()]

        return list(csv.DictReader(rows))
