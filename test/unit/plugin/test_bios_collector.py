# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import unittest
from unittest.mock import MagicMock

from errorscraper.config.config import SystemInteractionLevel
from errorscraper.datacollector.inband.bios import BiosCollector, BiosDataModel
from errorscraper.event import EventCategory
from errorscraper.systeminfo import SKU, OSFamily, SystemInfo
from errorscraper.taskresult import TaskStatus


class TestBiosCollector(unittest.TestCase):
    """Test the BiosCollector class."""

    def setUp(self):
        self.system_info = SystemInfo(
            name="test_host",
            sku=SKU.MI300X,
            platform="platform_id",
            os_family=OSFamily.LINUX,
        )
        self.ib_interface = MagicMock()
        self.collector = BiosCollector(
            system_info=self.system_info,
            system_interaction_level=SystemInteractionLevel.SURFACE,
            ib_interface=self.ib_interface,
        )

    def test_task_body_windows(self):
        """Test the _task_body method on Windows."""
        self.system_info.os_family = OSFamily.WINDOWS

        # Typical windows response.
        self.collector._run_system_command = MagicMock(
            return_value=MagicMock(
                exit_code=0,
                stdout="\n\nSMBIOSBIOSVersion=R23ET70W (1.40 )\n\n\n\n",
            )
        )

        exp_data = BiosDataModel(bios_version="R23ET70W (1.40 )")

        self.collector._log_event = MagicMock()
        res, data = self.collector.collect_data()
        self.assertEqual(data, exp_data)

    def test_task_body_linux(self):
        """Test the _task_body method on Linux."""
        self.system_info.os_family = OSFamily.LINUX
        # Typical linux response
        self.collector._run_system_command = MagicMock(
            return_value=MagicMock(
                exit_code=0,
                stdout="2.0.1",
            )
        )

        exp_data = BiosDataModel(bios_version="2.0.1")

        self.collector._log_event = MagicMock()
        res, data = self.collector.collect_data()
        self.assertEqual(data, exp_data)

    def test_task_body_error(self):
        """Test the _task_body method when an error occurs."""
        self.system_info.os_family = OSFamily.LINUX
        # bad exit code
        self.collector._run_system_command = MagicMock(
            return_value=MagicMock(
                exit_code=1,
                command="sh -c 'dmidecode -s bios-version'",
            )
        )
        res, data = self.collector.collect_data()
        self.assertEqual(res.status, TaskStatus.ERRORS_DETECTED)
        self.assertEqual(data, None)
        self.assertEqual(res.events[0].category, EventCategory.OS.value)
        self.assertEqual(res.events[0].description, "Error checking BIOS version")


if __name__ == "__main__":
    unittest.main()
