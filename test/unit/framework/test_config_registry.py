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

import os

from nodescraper.configregistry import ConfigRegistry
from nodescraper.models import PluginConfig


def test_config_registry():
    config_registry = ConfigRegistry(
        config_path=os.path.join(os.path.dirname(__file__), "fixtures", "valid_configs"),
        load_entry_point_configs=False,
    )

    assert config_registry.configs == {
        "ExampleConfig": PluginConfig(
            global_args={},
            plugins={"ExamplePlugin": {}},
            result_collators={},
            name="ExampleConfig",
            desc="This is an example",
        ),
        "example.json": PluginConfig(
            global_args={}, plugins={}, result_collators={}, name=None, desc=None
        ),
    }


def test_config_registry_raises_on_invalid_json(tmp_path):
    """A JSON file whose top level is not an object must be skipped, not crash the registry."""
    (tmp_path / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
    (tmp_path / "good.json").write_text('{"name": "GoodConfig", "plugins": {}}', encoding="utf-8")
    import pytest

    with pytest.raises(RuntimeError, match="Failed to load config from"):
        ConfigRegistry(
            config_path=str(tmp_path),
            load_entry_point_configs=False,
        )
