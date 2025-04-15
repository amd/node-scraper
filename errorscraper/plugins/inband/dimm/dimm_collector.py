from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .dimmdata import DimmDataModel


class DimmCollector(InBandDataCollector[DimmDataModel, None]):
    """Collect data on installed DIMMs"""

    DATA_MODEL = DimmDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, DimmDataModel | None]:
        """read DIMM data"""
        dimm_str = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic memorychip get Capacity")
            if res.exit_code == 0:
                capacities = {}
                total = 0
                for line in res.stdout.splitlines():
                    value = line.strip()
                    if value.isdigit():
                        value = int(value)
                        total += value
                        if value not in capacities:
                            capacities[value] = 1
                        else:
                            capacities[value] += 1
                dimm_str = f"{total / 1024 / 1024:.2f}GB @ "
                for capacity, count in capacities.items():
                    dimm_str += f"{count} x {capacity / 1024 / 1024:.2f}GB "
        else:
            res = self._run_sut_cmd(
                """sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\\|None\\|Module" | grep Size' 2>/dev/null""",
                sudo=True,
            )
            if res.exit_code == 0:
                total = 0
                topology = {}
                size = None
                for d in res.stdout.splitlines():
                    split = d.split()
                    size = split[2]
                    key = split[1] + split[2]
                    if not topology.get(key, None):
                        topology[key] = 1
                    else:
                        topology[key] += 1
                    num_gb = int(split[1])
                    total += num_gb
                topology["total"] = total
                topology["size"] = size
                total_gb = topology.pop("total")
                size = topology.pop("size")
                dimm_str = str(total_gb) + size + " @"
                for size, count in topology.items():
                    dimm_str += f" {count} x {size}"

        if res.exit_code != 0:
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

        if dimm_str:
            dimm_data = DimmDataModel(dimms=dimm_str)
            self._log_event(
                category=EventCategory.IO,
                description="Installed DIMM check",
                data=dimm_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"DIMM: {dimm_str}"
        else:
            dimm_data = None
            self._log_event(
                category=EventCategory.IO,
                description="DIMM info not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "DIMM info not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, dimm_data
