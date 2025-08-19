import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.inband.sysctl.analyzer_args import SysctlAnalyzerArgs
from nodescraper.plugins.inband.sysctl.sysctl_analyzer import SysctlAnalyzer
from nodescraper.plugins.inband.sysctl.sysctldata import SysctlDataModel


@pytest.fixture
def analyzer(system_info):
    return SysctlAnalyzer(system_info=system_info)


@pytest.fixture
def correct_data():
    return SysctlDataModel(
        vm_swappiness=1,
        vm_numa_balancing=2,
        vm_oom_kill_allocating_task=3,
        vm_compaction_proactiveness=4,
        vm_compact_unevictable_allowed=5,
        vm_extfrag_threshold=6,
        vm_zone_reclaim_mode=7,
        vm_dirty_background_ratio=8,
        vm_dirty_ratio=9,
        vm_dirty_writeback_centisecs=10,
        kernel_numa_balancing=11,
    )


def test_analyzer_all_match(analyzer, correct_data):
    args = SysctlAnalyzerArgs.build_from_model(correct_data)
    result = analyzer.analyze_data(correct_data, args)
    assert result.status == ExecutionStatus.OK


def test_analyzer_mismatch(analyzer, correct_data):
    args = SysctlAnalyzerArgs(exp_vm_swappiness=3, exp_vm_numa_balancing=4)
    result = analyzer.analyze_data(correct_data, args)
    assert result.status == ExecutionStatus.ERROR
    assert "Sysctl parameters mismatch detected" in result.message
