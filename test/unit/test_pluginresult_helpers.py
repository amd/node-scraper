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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models.datamodel import DataModel
from nodescraper.models.datapluginresult import DataPluginResult
from nodescraper.models.event import Event
from nodescraper.models.pluginresult import PluginResult
from nodescraper.models.taskresult import TaskResult


class MockDataModel(DataModel):
    """Mock data model for testing"""

    test_field: str = "test_data"


class TestPluginResultHelpers:
    """Test suite for PluginResult helper methods"""

    def test_get_system_data_with_data(self):
        """Test get_system_data when system data is available"""
        mock_data = MockDataModel(test_field="test_value")
        result_data = DataPluginResult(system_data=mock_data)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        system_data = plugin_result.get_system_data()
        assert system_data is not None
        assert system_data.test_field == "test_value"

    def test_get_system_data_without_data(self):
        """Test get_system_data when system data is not available"""
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=None
        )

        system_data = plugin_result.get_system_data()
        assert system_data is None

    def test_get_system_data_with_dict_result(self):
        """Test get_system_data when result_data is a dict (not BaseModel)"""
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data={"some": "data"}
        )

        system_data = plugin_result.get_system_data()
        assert system_data is None

    def test_get_analysis_events_with_events(self):
        """Test get_analysis_events when events are available"""
        events = [
            Event(
                category=EventCategory.RUNTIME,
                description="Test error",
                priority=EventPriority.ERROR,
            ),
            Event(
                category=EventCategory.RUNTIME,
                description="Test warning",
                priority=EventPriority.WARNING,
            ),
        ]
        analysis_result = TaskResult(status=ExecutionStatus.OK, events=events)
        result_data = DataPluginResult(analysis_result=analysis_result)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        retrieved_events = plugin_result.get_analysis_events()
        assert len(retrieved_events) == 2
        assert retrieved_events[0].description == "Test error"
        assert retrieved_events[1].description == "Test warning"

    def test_get_analysis_events_without_events(self):
        """Test get_analysis_events when no events are available"""
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=None
        )

        events = plugin_result.get_analysis_events()
        assert events == []

    def test_get_analysis_events_with_empty_list(self):
        """Test get_analysis_events when events list is empty"""
        analysis_result = TaskResult(status=ExecutionStatus.OK, events=[])
        result_data = DataPluginResult(analysis_result=analysis_result)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        events = plugin_result.get_analysis_events()
        assert events == []

    def test_get_artifact_files_with_collection_artifacts(self):
        """Test get_artifact_files with collection result artifacts"""
        collection_result = TaskResult(
            status=ExecutionStatus.OK, artifact_file_paths=["/tmp/file1.json", "/tmp/file2.log"]
        )
        result_data = DataPluginResult(collection_result=collection_result)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        files = plugin_result.get_artifact_files()
        assert len(files) == 2
        assert "/tmp/file1.json" in files
        assert "/tmp/file2.log" in files

    def test_get_artifact_files_with_analysis_artifacts(self):
        """Test get_artifact_files with analysis result artifacts"""
        analysis_result = TaskResult(
            status=ExecutionStatus.OK,
            artifact_file_paths=["/tmp/analysis1.json", "/tmp/analysis2.txt"],
        )
        result_data = DataPluginResult(analysis_result=analysis_result)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        files = plugin_result.get_artifact_files()
        assert len(files) == 2
        assert "/tmp/analysis1.json" in files
        assert "/tmp/analysis2.txt" in files

    def test_get_artifact_files_with_both_results(self):
        """Test get_artifact_files with both collection and analysis artifacts"""
        collection_result = TaskResult(
            status=ExecutionStatus.OK, artifact_file_paths=["/tmp/collection.json"]
        )
        analysis_result = TaskResult(
            status=ExecutionStatus.OK, artifact_file_paths=["/tmp/analysis.json"]
        )
        result_data = DataPluginResult(
            collection_result=collection_result, analysis_result=analysis_result
        )
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        files = plugin_result.get_artifact_files()
        assert len(files) == 2
        assert "/tmp/collection.json" in files
        assert "/tmp/analysis.json" in files

    def test_get_artifact_files_without_artifacts(self):
        """Test get_artifact_files when no artifacts are available"""
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=None
        )

        files = plugin_result.get_artifact_files()
        assert files == []

    def test_get_artifact_files_with_empty_paths(self):
        """Test get_artifact_files when artifact_file_paths is empty"""
        collection_result = TaskResult(status=ExecutionStatus.OK, artifact_file_paths=[])
        result_data = DataPluginResult(collection_result=collection_result)
        plugin_result = PluginResult(
            status=ExecutionStatus.OK, source="TestPlugin", result_data=result_data
        )

        files = plugin_result.get_artifact_files()
        assert files == []
