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
import logging

from nodescraper.models.pluginconfig import PluginConfig
from nodescraper.pluginexecutor import PluginExecutor


class TestPluginExecutorQuietMode:
    """Test suite for PluginExecutor quiet mode functionality"""

    def test_quiet_mode_creates_silent_logger(self):
        """Test that quiet=True creates a silent logger"""
        plugin_config = PluginConfig(name="test_config", plugins={})

        executor = PluginExecutor(plugin_configs=[plugin_config], quiet=True)

        # Verify logger is configured for silence
        assert executor.logger.level == logging.CRITICAL + 1
        assert len(executor.logger.handlers) == 1
        assert isinstance(executor.logger.handlers[0], logging.NullHandler)
        assert executor.logger.propagate is False

    def test_quiet_mode_false_uses_default_logger(self):
        """Test that quiet=False uses default logger"""
        plugin_config = PluginConfig(name="test_config", plugins={})

        executor = PluginExecutor(plugin_configs=[plugin_config], quiet=False)

        # Verify logger is the default logger
        assert "nodescraper" in executor.logger.name
        assert "silent" not in executor.logger.name

    def test_quiet_mode_default_is_false(self):
        """Test that default behavior is not quiet"""
        plugin_config = PluginConfig(name="test_config", plugins={})

        executor = PluginExecutor(plugin_configs=[plugin_config])

        # Verify logger is not in silent mode
        assert "silent" not in executor.logger.name

    def test_quiet_mode_with_custom_logger_provided(self):
        """Test that providing custom logger overrides quiet mode"""
        plugin_config = PluginConfig(name="test_config", plugins={})

        custom_logger = logging.getLogger("custom_test_logger")

        executor = PluginExecutor(
            plugin_configs=[plugin_config],
            logger=custom_logger,
            quiet=True,  # Should be ignored since logger is provided
        )

        # Verify the custom logger is used, not a silent one
        assert executor.logger.name == "custom_test_logger"

    def test_quiet_mode_with_log_path(self):
        """Test quiet mode still enables file logging when log_path is provided"""
        plugin_config = PluginConfig(name="test_config", plugins={})

        executor = PluginExecutor(
            plugin_configs=[plugin_config], quiet=True, log_path="/tmp/test_logs"
        )

        # Verify logger is silent
        assert executor.logger.level == logging.CRITICAL + 1

        # Verify file logging hook is still registered
        assert len(executor.connection_result_hooks) == 1
        assert executor.log_path == "/tmp/test_logs"
