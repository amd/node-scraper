import json
from pathlib import Path
from unittest.mock import MagicMock

from errorscraper.config.config import SystemInteractionLevel
from errorscraper.datacollector.inband.amdsmi import (
    AmdSmiCollector,
    AmdSmiData,
    AmdSmiTstData,
)
from errorscraper.datamodel.inband.amdsmidata import (
    AmdSmiListItem,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiVersion,
    BadPages,
    Fw,
    Processes,
    Topo,
)
from errorscraper.interfaces.inband import CommandArtifact, FileArtifact
from errorscraper.taskresult import TaskStatus
from scraper_test_base import ScraperTestBase


class TestAmdSmiCollection(ScraperTestBase):
    """Test the amdsmi collector"""

    def setUp(self) -> None:
        super().setUp()
        json_text = (Path(self.fixtures_path) / "test_amdsmi_collector_mi355.json").read_text()
        self.fixture_dict = json.loads(json_text)
        self.test_collector = AmdSmiCollector(
            system_info=self.system_info_mi300x,
            system_interaction_level=SystemInteractionLevel.STANDARD,
            ib_interface=self.ib_interface,
        )

        self.ib_interface.run_command = MagicMock()
        self.ib_interface.run_command.side_effect = self.mock_with_fixture

    def mock_with_fixture(self, *args, **kwargs):
        """Mock the interface to return the fixture data"""
        for artifact in self.fixture_dict:
            a_cmd = artifact["command"]
            a_cmd_sudo_pass = f"sudo -S -p '' {kwargs['command']}"
            a_cmd_sudo = f"sudo {kwargs['command']}"
            if a_cmd == kwargs["command"] or a_cmd_sudo == a_cmd or a_cmd == a_cmd_sudo_pass:
                return CommandArtifact(**artifact)

    def test_data_collection_config(self) -> None:
        """Test checks for the tool being installed and that the check aborts with the proper
        task status when amd-smi is not installed"""
        self.ib_interface.run_command.return_value = CommandArtifact(
            command="which amd-smi",
            stdout="/usr/bin/amd-smi",
            stderr="",
            exit_code=0,
        )
        is_installed = self.test_collector._check_amdsmi_installed()
        self.assertTrue(is_installed)
        self.ib_interface.run_command.side_effect = None
        self.ib_interface.run_command.return_value = CommandArtifact(
            command="which amd-smi",
            stdout="",
            stderr="command not found",
            exit_code=1,
        )
        is_installed = self.test_collector._check_amdsmi_installed()
        self.assertFalse(is_installed)

        res, data = self.test_collector.collect_data()
        self.assertEqual(res.status, TaskStatus.NOT_RAN)
        self.assertIsNone(data)

    def test_amd_smi_data_and_commands(self) -> None:
        """Test basic AMD SMI data collection that all methods return correct types"""
        amd_smi_return_dict_cmds = {
            "gpu_list": (self.test_collector.get_gpu_list, AmdSmiListItem),
            "process": (self.test_collector.get_process, Processes),
            "topology": (self.test_collector.get_topology, Topo),
            "static": (self.test_collector.get_static, AmdSmiStatic),
            "metric": (self.test_collector.get_metric, AmdSmiMetric),
            "firmware": (self.test_collector.get_firmware, Fw),
            "bad_pages": (self.test_collector.get_bad_pages, BadPages),
        }
        result_data = {}
        self.test_collector.amd_smi_commands = self.test_collector.detect_amdsmi_commands()
        for cmd_name, amd_smi_cmd_obj in amd_smi_return_dict_cmds.items():
            result_data[cmd_name] = amd_smi_cmd_obj[0]()

            data = amd_smi_cmd_obj[1](**result_data[cmd_name][0])
            self.assertIsInstance(data, amd_smi_cmd_obj[1])
            self.assertIsNotNone(result_data[cmd_name])

    def test_amd_smi_mi325(self):
        json_text = (Path(self.fixtures_path) / "test_amdsmi_collector_mi325.json").read_text()
        self.fixture_dict = json.loads(json_text)

        res, data = self.test_collector.collect_data()
        self.assertEqual(res.status, TaskStatus.OK)
        self.assertIsInstance(data, AmdSmiData)
        # Check
        self.assertEqual(data.gpu_list[0].bdf, "0000:09:00.0")
        self.assertEqual(
            data.process[0].process_list[0].process_info.name,
            "rvs",
        )
        self.assertEqual(
            data.process[0].process_list[0].process_info.pid,
            206506,
        )
        self.assertEqual(data.get_topology(0).links[0].num_hops, 0)
        self.assertEqual(data.get_static(0).asic.device_id, "0x74a5")
        self.assertEqual(data.metric[0].pcie.width, 16)
        self.assertEqual(data.firmware[0].fw_list[0].fw_version, "177")
        self.assertEqual(data.bad_pages[0].retired, "No bad pages found.")
        self.assertEqual(data.xgmi_link[0].bdf, "0000:09:00.0")
        self.assertEqual(data.xgmi_metric[0].link_metrics.bit_rate.value, 32)

    def test_amd_smi_tst_data(self) -> None:
        """Test the AMD SMI test data collection, ensure it can built list and counts of tests of each status"""
        # Example takes pertinent snippets from actual full output
        self.test_collector.system_interaction_level = SystemInteractionLevel.DISRUPTIVE
        version_data_pass = AmdSmiVersion(
            tool="AMDSMI Tool",
            version="25.5.1+c11e6492",
            amdsmi_library_version="25.5.1",
            rocm_version="6.4.2",
            amdgpu_version="6.12.12",
            amd_hsmp_driver_version="N/A",
        )
        version_data_old = AmdSmiVersion(
            tool="AMDSMI Tool",
            version="25.5.1+c11e6492",
            amdsmi_library_version="25.5.1",
            rocm_version="6.4.0",
            amdgpu_version="6.12.12",
            amd_hsmp_driver_version="N/A",
        )

        amdsmitst_data = self.test_collector.get_amdsmitst_data(version_data_old)
        self.assertIsInstance(amdsmitst_data, AmdSmiTstData)
        self.assertEqual(amdsmitst_data.passed_test_count, 0)
        self.assertEqual(amdsmitst_data.failed_test_count, 0)
        self.assertEqual(amdsmitst_data.skipped_test_count, 0)
        amdsmitst_data = self.test_collector.get_amdsmitst_data(version_data_pass)
        self.assertIsInstance(amdsmitst_data, AmdSmiTstData)
        self.assertEqual(amdsmitst_data.passed_test_count, 3)
        self.assertEqual(amdsmitst_data.failed_test_count, 2)
        self.assertEqual(amdsmitst_data.skipped_test_count, 1)
        self.assertTrue("amdsmitstReadOnly.TestVersionRead" in amdsmitst_data.passed_tests)
        self.assertTrue("amdsmitstReadWrite.TestXGMIReadWrite" in amdsmitst_data.skipped_tests)
        self.assertTrue("amdsmitstReadWrite.TestPerfDeterminism" in amdsmitst_data.failed_tests)
        self.ib_interface.run_command.side_effect = None

        self.ib_interface.run_command.return_value = CommandArtifact(
            command="/opt/rocm/share/amd_smi_tests/amdsmitsts/",
            stdout="",
            stderr="No such file or directory",
            exit_code=255,
        )
        amdsmitst_data = self.test_collector.get_amdsmitst_data(version_data_pass)
        self.assertEqual(amdsmitst_data, AmdSmiTstData())

    def test_task_body_bad_data_collected(self):
        """Test the task body when the data collection fails"""
        self.ib_interface.run_command.side_effect = [
            CommandArtifact(
                command="which amd-smi",
                stdout="/usr/bin/amd-smi",
                stderr="",
                exit_code=0,
            )
        ] * 100
        res, data = self.test_collector.collect_data()
        self.assertEqual(res.status, TaskStatus.ERRORS_DETECTED)
        self.assertIsInstance(data, AmdSmiData)
        self.assertEqual(
            res.events[0].description,
            "Error parsing command: `version --json` json data",
        )

    def test_amdsmi_collector_350(self):
        """Test the AMD SMI collector with a MI350x fixture"""
        json_text = (Path(self.fixtures_path) / "test_amdsmi_collector_mi350.json").read_text()
        self.fixture_dict = json.loads(json_text)
        fixture_tar_file = Path(self.fixtures_path) / "amd_smi_cper.tar.gz"
        with open(fixture_tar_file, "rb") as f:
            tar_bytes = f.read()
        self.ib_interface.read_file.return_value = FileArtifact(
            filename="amd_smi_cper.tar.gz",
            contents=tar_bytes,
        )

        res, data = self.test_collector.collect_data()
        self.assertEqual(res.status, TaskStatus.OK)
        self.assertIsInstance(data, AmdSmiData)
        self.assertIsNotNone(data.gpu_list)
        self.assertIsNotNone(data.process)
        self.assertIsNotNone(data.topology)
        self.assertIsNotNone(data.static)
        self.assertIsNotNone(data.metric)
        self.assertIsNotNone(data.firmware)
        self.assertIsNotNone(data.bad_pages)
        self.assertIsNotNone(data.xgmi_metric)
        self.assertIsNotNone(data.xgmi_link)
        self.assertIsNotNone(data.cper_data)

    def test_amdsmi_cper_collection(self):
        """Test the AMD SMI collector with a MI350x fixture for CPER collection"""
        fixture_tar_file = Path(self.fixtures_path) / "amd_smi_cper.tar.gz"
        self.ib_interface.run_command.side_effect = [
            CommandArtifact(
                command="which amd-smi",
                stdout="/usr/bin/amd-smi",
                stderr="",
                exit_code=0,
            ),
            CommandArtifact(
                command="sudo -S -p '' amd-smi ras --cper --folder=/tmp/amd_smi_cper --afid",
                stdout="""Dumping CPER file header entries in folder /tmp/cpers
                    timestamp            gpu_id  severity     file_name
                    2025/06/17 21:45:30  0       corrected    corrected_0.cper
                    """,
                stderr="",
                exit_code=0,
            ),
            CommandArtifact(
                command="tar -czf /tmp/amd_smi_cper.tar.gz -C /tmp/amd_smi_cper .",
                stdout="tar",
                stderr="",
                exit_code=0,
            ),
        ]
        # read tar file into bytes
        with open(fixture_tar_file, "rb") as f:
            tar_bytes = f.read()
        self.ib_interface.read_file.return_value = FileArtifact(
            filename="amd_smi_cper.tar.gz",
            contents=tar_bytes,
        )
        self.test_collector.amd_smi_commands = {"ras"}
        amd_data = self.test_collector.get_cper_data()

        self.assertEqual(len(amd_data), 1)
        self.assertEqual(len(amd_data[0].file_contents), 4256)
        self.assertEqual(amd_data[0].file_name, "./corrected_0.cper")

    def test_amdsmi_cper_no_cpers(self):
        """Test the AMD SMI collector with a MI350x fixture for CPER collection with no CPER data"""
        self.ib_interface.run_command.side_effect = [
            CommandArtifact(
                command="which amd-smi",
                stdout="/usr/bin/amd-smi",
                stderr="",
                exit_code=0,
            ),
            CommandArtifact(
                command="mkdir -p /tmp/amd_smi_cper && rm /tmp/amd_smi_cper/*.cper && rm /tmp/amd_smi_cper/*.json",
                stdout="",
                stderr="",
                exit_code=0,
            ),
            CommandArtifact(
                command="sudo -S -p '' amd-smi ras --cper --folder=/tmp/amd_smi_cper --afid",
                stdout="""Dumping CPER file header entries in folder /tmp/cpers
                    timestamp            gpu_id  severity     file_name

                    """,
                stderr="",
                exit_code=0,
            ),
        ]
        self.test_collector.amd_smi_commands = {"ras"}

        amd_data = self.test_collector.get_cper_data()
        self.assertEqual(len(amd_data), 0)

    def test_detect_amdsmi_commands(self):
        """Test the detection of AMD SMI commands"""
        self.ib_interface.run_command.side_effect = [
            CommandArtifact(
                command="amd-smi -h",
                stdout="AMD System Management Interface | Version: 25.3.0+ede62f2 | ROCm version: 6.4.0 |\nPlatform: Linux Baremetal\n\noptions:\n  -h, --help          show this help message and exit\n\nAMD-SMI Commands:\n                      Descriptions:\n    version           Display version information\n    list              List GPU information\n    static            Gets static information about the specified GPU\n    firmware (ucode)  Gets firmware information about the specified GPU\n    bad-pages         Gets bad page information about the specified GPU\n    metric            Gets metric/performance information about the specified GPU\n    process           Lists general process information running on the specified GPU\n    event             Displays event information for the given GPU\n    topology          Displays topology information of the devices\n    set               Set options for devices\n    reset             Reset options for devices\n    monitor (dmon)    Monitor metrics for target devices\n    xgmi              Displays xgmi information of the devices\n    partition         Displays partition information of the devices\n",
                stderr="",
                exit_code=0,
            ),
        ]
        commands = self.test_collector.detect_amdsmi_commands()
        self.assertEqual(
            commands,
            {
                "version",
                "list",
                "static",
                "firmware",
                "bad-pages",
                "metric",
                "process",
                "event",
                "topology",
                "set",
                "reset",
                "monitor",
                "xgmi",
                "partition",
            },
        )
