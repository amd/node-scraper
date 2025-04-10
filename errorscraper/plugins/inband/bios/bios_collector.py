# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.interfaces.inbandcollectortask import InBandDataCollector
from errorscraper.models import TaskResult

from .biosdata import BiosDataModel


class BiosCollector(InBandDataCollector[BiosDataModel, None]):
    """Collect BIOS details"""

    DATA_MODEL = BiosDataModel

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, BiosDataModel | None]:
        """read bios data"""
        bios = None

        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic bios get SMBIOSBIOSVersion /Value")
            if res.exit_code == 0:
                bios = [line for line in res.stdout.splitlines() if "SMBIOSBIOSVersion=" in line][
                    0
                ].split("=")[1]
        else:
            res = self._run_sut_cmd("sh -c 'dmidecode -s bios-version'", sudo=True)
            if res.exit_code == 0:
                bios = res.stdout

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking BIOS version",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if bios:
            bios_data = BiosDataModel(bios_version=bios)
            self._log_event(
                category="BIOS_READ",
                description="BIOS version read",
                data=bios_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"BIOS: {bios}"
        else:
            bios_data = None
            self._log_event(
                category=EventCategory.BIOS,
                description="BIOS version not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "BIOS version not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, bios_data
