from unittest.mock import MagicMock, patch

import pytest

from errorscraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from errorscraper.interfaces.connectionmanager import ConnectionManager
from errorscraper.interfaces.dataanalyzertask import DataAnalyzer
from errorscraper.interfaces.datacollectortask import DataCollector
from errorscraper.interfaces.dataplugin import DataPlugin
from errorscraper.models import DataModel, TaskResult


class StandardDataModel(DataModel):
    value: str = "test"


class MockConnectionManager(ConnectionManager):
    # Class variable to store the mock connector
    mock_connector = None

    def __init__(
        self, system_info=None, logger=None, parent=None, task_hooks=None, connection_args=None
    ):
        super().__init__(
            system_info=system_info,
            logger=logger,
            parent=parent,
            task_hooks=task_hooks,
            connection_args=connection_args,
        )
        # Use the class variable if available, otherwise create a new MagicMock
        self.connection = (
            MockConnectionManager.mock_connector
            if MockConnectionManager.mock_connector
            else MagicMock()
        )
        self.result = TaskResult(status=ExecutionStatus.OK)

    def connect(self):
        self.result.status = ExecutionStatus.OK
        return self.result

    def disconnect(self):
        return TaskResult(status=ExecutionStatus.OK)


class BaseDataCollector(DataCollector):
    DATA_MODEL = StandardDataModel

    def collect_data(self, args=None):
        return TaskResult(status=ExecutionStatus.OK), StandardDataModel()


class StandardAnalyzer(DataAnalyzer):
    DATA_MODEL = StandardDataModel

    def analyze_data(self, data, args=None):
        return TaskResult(status=ExecutionStatus.OK)


class CoreDataPlugin(DataPlugin):
    DATA_MODEL = StandardDataModel
    CONNECTION_TYPE = MockConnectionManager
    COLLECTOR = BaseDataCollector
    ANALYZER = StandardAnalyzer


@pytest.fixture(autouse=True)
def setup_mock_connector(conn_mock):
    # Set the class variable to the conn_mock fixture
    MockConnectionManager.mock_connector = conn_mock
    yield
    # Reset after the test
    MockConnectionManager.mock_connector = None


@pytest.fixture
def mock_connection_manager(system_info, logger, conn_mock):
    manager = MockConnectionManager(system_info=system_info, logger=logger)
    manager.connection = conn_mock
    return manager


@pytest.fixture
def plugin(system_info, logger):
    return CoreDataPlugin(system_info=system_info, logger=logger)


@pytest.fixture
def plugin_with_conn(system_info, logger, mock_connection_manager):
    return CoreDataPlugin(
        system_info=system_info, logger=logger, connection_manager=mock_connection_manager
    )


class TestDataPluginCore:
    """Tests for the DataPlugin interface"""

    def test_init(self, system_info, logger, mock_connection_manager):
        # Test initialization without connection manager
        plugin = CoreDataPlugin(system_info=system_info, logger=logger)

        # Verify basic initialization
        assert plugin.system_info == system_info
        assert plugin.logger == logger
        assert plugin.data is None
        assert plugin.collection_result.status == ExecutionStatus.NOT_RAN
        assert plugin.analysis_result.status == ExecutionStatus.NOT_RAN
        assert plugin.connection_manager is None

        # Test initialization with connection manager
        plugin_with_conn = CoreDataPlugin(
            system_info=system_info, logger=logger, connection_manager=mock_connection_manager
        )
        assert plugin_with_conn.connection_manager is mock_connection_manager

    def test_data_property(self, plugin):
        # Test setting with model instance
        data = StandardDataModel(value="test_value")
        plugin.data = data
        assert plugin.data == data
        assert plugin.data.value == "test_value"

        # Test setting with dictionary
        plugin.data = {"value": "dict_value"}
        assert isinstance(plugin.data, StandardDataModel)
        assert plugin.data.value == "dict_value"

    def test_collect_creates_connection_manager(self, plugin, conn_mock):
        assert plugin.connection_manager is None

        with patch.object(BaseDataCollector, "collect_data") as mock_collect:
            mock_collect.return_value = (TaskResult(status=ExecutionStatus.OK), StandardDataModel())
            result = plugin.collect()

            assert plugin.connection_manager is not None
            assert isinstance(plugin.connection_manager, MockConnectionManager)
            assert plugin.connection_manager.connection is conn_mock
            mock_collect.assert_called_once()
            assert result.status == ExecutionStatus.OK

    def test_collect_with_connection_manager(self, plugin_with_conn):
        with patch.object(BaseDataCollector, "collect_data") as mock_collect:
            mock_collect.return_value = (TaskResult(status=ExecutionStatus.OK), StandardDataModel())
            result = plugin_with_conn.collect()

            mock_collect.assert_called_once()
            assert result.status == ExecutionStatus.OK

    def test_analyze(self, plugin_with_conn):
        plugin_with_conn.data = StandardDataModel(value="test_data")

        with patch.object(StandardAnalyzer, "analyze_data") as mock_analyze:
            mock_analyze.return_value = TaskResult(status=ExecutionStatus.OK)
            result = plugin_with_conn.analyze()

            mock_analyze.assert_called_once()
            assert result.status == ExecutionStatus.OK

    def test_analyze_with_args_and_data(self, plugin_with_conn):
        plugin_with_conn.data = StandardDataModel(value="internal_data")

        test_cases = [
            # (analysis_args, data, description)
            ("test_args", None, "with args only"),
            (None, StandardDataModel(value="external_data"), "with data only"),
            ("test_args", StandardDataModel(value="external_data"), "with both args and data"),
        ]

        for args, data, _desc in test_cases:
            with patch.object(StandardAnalyzer, "analyze_data") as mock_analyze:
                mock_analyze.return_value = TaskResult(status=ExecutionStatus.OK)

                kwargs = {}
                if args:
                    kwargs["analysis_args"] = args
                if data:
                    kwargs["data"] = data

                result = plugin_with_conn.analyze(**kwargs)

                mock_analyze.assert_called_once()
                assert result.status == ExecutionStatus.OK

    def test_run_creates_connection_manager(self, plugin):
        assert plugin.connection_manager is None

        with (
            patch.object(CoreDataPlugin, "collect") as mock_collect,
            patch.object(CoreDataPlugin, "analyze") as mock_analyze,
        ):

            mock_collect.return_value = TaskResult(status=ExecutionStatus.OK)
            mock_analyze.return_value = TaskResult(status=ExecutionStatus.OK)

            def collect_side_effect(*args, **kwargs):
                result = TaskResult(status=ExecutionStatus.OK)
                plugin.collection_result = result
                plugin.data = StandardDataModel(value="collected")
                return result

            def analyze_side_effect(*args, **kwargs):
                result = TaskResult(status=ExecutionStatus.OK)
                plugin.analysis_result = result
                return result

            mock_collect.side_effect = collect_side_effect
            mock_analyze.side_effect = analyze_side_effect

            result = plugin.run()

            mock_collect.assert_called_once()
            mock_analyze.assert_called_once()
            assert result.status == ExecutionStatus.OK
            assert result.result_data.system_data == plugin.data
            assert result.result_data.collection_result == plugin.collection_result
            assert result.result_data.analysis_result == plugin.analysis_result

    @pytest.mark.parametrize(
        "collection,analysis,expected_calls",
        [
            (True, False, (1, 0)),  # collection only
            (False, True, (0, 1)),  # analysis only
            (True, True, (1, 1)),  # both
        ],
    )
    def test_run_execution_modes(self, plugin_with_conn, collection, analysis, expected_calls):
        if analysis:
            plugin_with_conn.data = StandardDataModel()  # Set data so analysis can run

        with (
            patch.object(CoreDataPlugin, "collect") as mock_collect,
            patch.object(CoreDataPlugin, "analyze") as mock_analyze,
        ):

            mock_collect.return_value = TaskResult(status=ExecutionStatus.OK)
            mock_analyze.return_value = TaskResult(status=ExecutionStatus.OK)

            plugin_with_conn.run(collection=collection, analysis=analysis)

            assert mock_collect.call_count == expected_calls[0]
            assert mock_analyze.call_count == expected_calls[1]

    def test_run_with_parameters(self, plugin_with_conn):
        collection_args = {"param": "value"}
        analysis_args = {"threshold": 0.5}
        data = StandardDataModel(value="external_data")

        with (
            patch.object(CoreDataPlugin, "collect") as mock_collect,
            patch.object(CoreDataPlugin, "analyze") as mock_analyze,
        ):

            mock_collect.return_value = TaskResult(status=ExecutionStatus.OK)
            mock_analyze.return_value = TaskResult(status=ExecutionStatus.OK)

            plugin_with_conn.run(
                collection=True,
                analysis=True,
                max_event_priority_level=EventPriority.ERROR,
                system_interaction_level=SystemInteractionLevel.PASSIVE,
                preserve_connection=True,
                data=data,
                collection_args=collection_args,
                analysis_args=analysis_args,
            )

            mock_collect.assert_called_once_with(
                max_event_priority_level=EventPriority.ERROR,
                system_interaction_level=SystemInteractionLevel.PASSIVE,
                collection_args=collection_args,
                preserve_connection=True,
            )

            mock_analyze.assert_called_once_with(
                max_event_priority_level=EventPriority.ERROR, analysis_args=analysis_args, data=data
            )

    def test_collect_preserve_connection(self, plugin_with_conn):
        """Test the behavior of preserve_connection parameter in collect method."""
        # Test with preserve_connection=True
        with patch.object(BaseDataCollector, "collect_data") as mock_collect:
            with patch.object(MockConnectionManager, "disconnect") as mock_disconnect:
                mock_collect.return_value = (
                    TaskResult(status=ExecutionStatus.OK),
                    StandardDataModel(),
                )

                # Call collect with preserve_connection=True
                result = plugin_with_conn.collect(preserve_connection=True)

                # Verify collect_data was called and result is OK
                mock_collect.assert_called_once()
                assert result.status == ExecutionStatus.OK

                # Verify disconnect was NOT called when preserve_connection=True
                mock_disconnect.assert_not_called()

        # Test with preserve_connection=False (default)
        with patch.object(BaseDataCollector, "collect_data") as mock_collect:
            with patch.object(MockConnectionManager, "disconnect") as mock_disconnect:
                mock_collect.return_value = (
                    TaskResult(status=ExecutionStatus.OK),
                    StandardDataModel(),
                )

                # Call collect with preserve_connection=False (default)
                result = plugin_with_conn.collect(preserve_connection=False)

                # Verify collect_data was called and result is OK
                mock_collect.assert_called_once()
                assert result.status == ExecutionStatus.OK

                # Verify disconnect WAS called when preserve_connection=False
                mock_disconnect.assert_called_once()
