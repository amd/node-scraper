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
import datetime
import re
from typing import Optional

from nodescraper.base.regexanalyzer import ErrorRegex, RegexAnalyzer
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority
from nodescraper.models import Event, TaskResult

from .analyzer_args import DmesgAnalyzerArgs
from .dmesgdata import DmesgData


class DmesgAnalyzer(RegexAnalyzer[DmesgData, DmesgAnalyzerArgs]):
    """Check dmesg for errors"""

    DATA_MODEL = DmesgData

    ERROR_REGEX: list[ErrorRegex] = [
        ErrorRegex(
            regex=re.compile(r"(?:oom_kill_process.*)|(?:Out of memory.*)"),
            message="Out of memory error",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"IO_PAGE_FAULT"),
            message="I/O Page Fault",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"\bkernel panic\b.*", re.IGNORECASE),
            message="Kernel Panic",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"sq_intr"),
            message="SQ Interrupt",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"sram_ecc.*"),
            message="SRAM ECC",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"\[amdgpu\]\] \*ERROR\* hw_init of IP block.*"),
            message="Failed to load driver. IP hardware init error.",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"\[amdgpu\]\] \*ERROR\* sw_init of IP block.*"),
            message="Failed to load driver. IP software init error.",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"sched: RT throttling activated.*"),
            message="Real Time throttling activated",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"rcu_preempt detected stalls.*"),
            message="RCU preempt detected stalls",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"rcu_preempt self-detected stall.*"),
            message="RCU preempt self-detected stall",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"qcm fence wait loop timeout.*"),
            message="QCM fence timeout",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"(?:[\w-]+(?:\[[0-9.]+\])?\s+)?general protection fault[^\n]*"),
            message="General protection fault",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:segfault.*in .*\[)|(?:[Ss]egmentation [Ff]ault.*)|(?:[Ss]egfault.*)"
            ),
            message="Segmentation fault",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"amdgpu: Failed to disallow cf state.*"),
            message="Failed to disallow cf state",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"\*ERROR\* Failed to terminate tmr.*"),
            message="Failed to terminate tmr",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"\*ERROR\* suspend of IP block <\w+> failed.*"),
            message="Suspend of IP block failed",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(
                (
                    r"(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:\s+\[\S+\]\s*(?:retry|no-retry)? page fault[^\n]*)"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                    r"(?:\n[^\n]*(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:[^\n]*))?"
                ),
                re.MULTILINE,
            ),
            message="amdgpu Page Fault",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile((r"page fault for address.*")),
            message="Page Fault",
            event_category=EventCategory.OS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:amdgpu)(.*Fatal error during GPU init)|(Fatal error during GPU init)"
            ),
            message="Fatal error during GPU init",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"(?:pcieport )(.*AER: aer_status.*)|(aer_status.*)"),
            message="PCIe AER Error",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"Failed to read journal file.*"),
            message="Failed to read journal file",
            event_category=EventCategory.OS,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(r"journal corrupted or uncleanly shut down.*"),
            message="Journal file corrupted or uncleanly shut down",
            event_category=EventCategory.OS,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(r"ACPI BIOS Error"),
            message="ACPI BIOS Error",
            event_category=EventCategory.BIOS,
        ),
        ErrorRegex(
            regex=re.compile(r"ACPI Error"),
            message="ACPI Error",
            event_category=EventCategory.BIOS,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(r"EXT4-fs error \(device .*\):"),
            message="Filesystem corrupted!",
            event_category=EventCategory.OS,
        ),
        ErrorRegex(
            regex=re.compile(r"(Buffer I\/O error on dev)(?:ice)? (\w+)"),
            message="Error in buffered IO, check filesystem integrity",
            event_category=EventCategory.IO,
        ),
        ErrorRegex(
            regex=re.compile(
                r"pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(\d+\)):\s+(Card not present)"
            ),
            message="PCIe card no longer present",
            event_category=EventCategory.IO,
        ),
        ErrorRegex(
            regex=re.compile(
                r"pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(\d+\)):\s+(Link Down)"
            ),
            message="PCIe Link Down",
            event_category=EventCategory.IO,
        ),
        ErrorRegex(
            regex=re.compile(
                r"pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(current common clock configuration is inconsistent, reconfiguring)"
            ),
            message="Mismatched clock configuration between PCIe device and host",
            event_category=EventCategory.IO,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.* correctable hardware errors detected in total in \w+ block.*)"
            ),
            message="RAS Correctable Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.* uncorrectable hardware errors detected in \w+ block.*)"
            ),
            message="RAS Uncorrectable Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.* deferred hardware errors detected in \w+ block.*)"
            ),
            message="RAS Deferred Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"((?:\[Hardware Error\]:\s+)?event severity: corrected.*)"
                r"\n.*(\[Hardware Error\]:\s+Error \d+, type: corrected.*)"
                r"\n.*(\[Hardware Error\]:\s+section_type: PCIe error.*)"
            ),
            message="RAS Corrected PCIe Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.*GPU reset begin.*)"),
            message="GPU Reset",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.*GPU reset(?:\(\d+\))? failed.*)"
            ),
            message="GPU reset failed",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                (
                    r"(Accelerator Check Architecture[^\n]*)"
                    r"(?:\n[^\n]*){0,10}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*entry\[\d+\]\.STATUS=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*entry\[\d+\]\.ADDR=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*entry\[\d+\]\.MISC0=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*entry\[\d+\]\.IPID=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*entry\[\d+\]\.SYND=0x[0-9a-fA-F]+-?)"
                ),
                re.MULTILINE,
            ),
            message="ACA Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                (
                    r"(Accelerator Check Architecture[^\n]*)"
                    r"(?:\n[^\n]*){0,10}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*CONTROL=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*STATUS=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*ADDR=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*MISC=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*CONFIG=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*IPID=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*SYND=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*DESTAT=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*DEADDR=0x[0-9a-fA-F]+)"
                    r"(?:\n[^\n]*){0,5}?"
                    r"(amdgpu[ 0-9a-fA-F:.]+:? [^\n]*CONTROL_MASK=0x[0-9a-fA-F]+)"
                ),
                re.MULTILINE,
            ),
            message="ACA Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(r"\[Hardware Error\]:.+MC\d+_STATUS.*(?:\n.*){0,5}"),
            message="MCE Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)? (.*Mode2 reset failed.*)"
            ),
            message="Mode 2 Reset Failed",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(.*\[Hardware Error\]: Corrected error.*)"
            ),
            message="RAS Corrected Error",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(r"x86/cpu: SGX disabled by BIOS"),
            message="SGX Error",
            event_category=EventCategory.BIOS,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(r"amdgpu \w{4}:\w{2}:\w{2}.\w: amdgpu: WARN: GPU is throttled.*"),
            message="GPU Throttled",
            event_category=EventCategory.SW_DRIVER,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\[[^\]]+\]\s*)?LNetError:.*ko2iblnd:\s*No matching interfaces",
                re.IGNORECASE,
            ),
            message="LNet: ko2iblnd has no matching interfaces",
            event_category=EventCategory.IO,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(
                r"(?:\[[^\]]+\]\s*)?LNetError:\s*.*Error\s*-?\d+\s+starting up LNI\s+\w+",
                re.IGNORECASE,
            ),
            message="LNet: Error starting up LNI",
            event_category=EventCategory.IO,
            event_priority=EventPriority.WARNING,
        ),
        ErrorRegex(
            regex=re.compile(
                r"LustreError:.*ptlrpc_init_portals\(\).*network initiali[sz]ation failed",
                re.IGNORECASE,
            ),
            message="Lustre: network initialisation failed",
            event_category=EventCategory.IO,
            event_priority=EventPriority.WARNING,
        ),
    ]

    @classmethod
    def filter_dmesg(
        cls,
        dmesg_content: str,
        analysis_range_start: Optional[datetime.datetime] = None,
        analysis_range_end: Optional[datetime.datetime] = None,
    ) -> str:
        """Filter a dmesg log by date

        Args:
            dmesg_content (str): unfiltered dmesg log

        Returns:
            str: filterd dmesg log
        """

        filtered_dmesg = ""
        found_start = False if analysis_range_start else True
        for line in dmesg_content.splitlines():
            date = re.search(r"(\d{4}-\d+-\d+T\d+:\d+:\d+),(\d+[+-]\d+:\d+)", line)
            if date is not None:
                date = datetime.datetime.fromisoformat(f"{date.group(1)}.{date.group(2)}")
                # show date in UTC now
                date = date.astimezone(datetime.timezone.utc)
                if analysis_range_start and not found_start and date >= analysis_range_start:
                    found_start = True
                elif analysis_range_end and date >= analysis_range_end:
                    break

                # only read lines after starting timestamp is found, ignore lines that do not have valid date
                if found_start:
                    filtered_dmesg += f"{line}\n"

        return filtered_dmesg

    def _is_known_error(self, known_err_events: list[Event], unknown_match: str) -> bool:
        """Check if a potential unknown error line has a known regex

        Args:
            known_err_events (list[Event]): list of events from known regex
            unknown_match (str): unknown match string

        Returns:
            bool: return True if error is known
        """
        for regex_obj in self.ERROR_REGEX:
            if regex_obj.regex.search(unknown_match):
                return True

        # handle multline matches
        for event in known_err_events:
            known_match = event.data["match_content"]
            if isinstance(known_match, list):
                for line in known_match:
                    if unknown_match in line:
                        return True
            elif known_match in unknown_match:
                return True
        return False

    def analyze_data(
        self,
        data: DmesgData,
        args: Optional[DmesgAnalyzerArgs] = None,
    ) -> TaskResult:
        """Analyze dmesg data for errors

        Args:
            data (DmesgData): dmesg data to analyze
            args (Optional[DmesgAnalyzerArgs], optional): dmesg analysis arguments. Defaults to None.

        Returns:
            TaskResult: The result of the analysis containing status and message.
        """

        if not args:
            args = DmesgAnalyzerArgs()

        if args.analysis_range_start or args.analysis_range_end:
            self.logger.info(
                "Filtering dmesg using range %s - %s",
                args.analysis_range_start,
                args.analysis_range_end,
            )
            dmesg_content = self.filter_dmesg(
                data.dmesg_content,
                args.analysis_range_start,
                args.analysis_range_end,
            )
            self.result.artifacts.append(
                TextFileArtifact(filename="filtered_dmesg.log", contents=dmesg_content)
            )
        else:
            dmesg_content = data.dmesg_content

        known_err_events = self.check_all_regexes(
            content=dmesg_content, source="dmesg", error_regex=self.ERROR_REGEX
        )
        if args.exclude_category:
            known_err_events = [
                event for event in known_err_events if event.category not in args.exclude_category
            ]

        self.result.events += known_err_events

        if args.check_unknown_dmesg_errors:
            err_events = self.check_all_regexes(
                content=dmesg_content,
                source="dmesg",
                error_regex=[
                    ErrorRegex(
                        regex=re.compile(
                            r"kern  :(?:err|crit|alert|emerg)\s+: \d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+ (.*)"
                        ),
                        message="Unknown dmesg error",
                        event_category=EventCategory.UNKNOWN,
                        event_priority=EventPriority.WARNING,
                    )
                ],
            )

            for err_event in err_events:
                match_content = err_event.data["match_content"]
                if not self._is_known_error(known_err_events, match_content):
                    self.result.events.append(err_event)

        return self.result
