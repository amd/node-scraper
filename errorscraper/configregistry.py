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
import json
import os
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from errorscraper.models import PluginConfig


class ConfigRegistry:
    """Class to load json plugin configs into models"""

    INTERNAL_SEARCH_PATH = os.path.join(os.path.dirname(__file__), "configs")

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.configs = {}
        self.load_configs(config_path)

    def load_configs(self, config_path: Optional[str] = None):
        """load plugin config json files into pydantic models

        Args:
            config_path (Optional[str], optional): Path in which to search for config files. Defaults to None.
        """
        if not config_path:
            config_path = self.INTERNAL_SEARCH_PATH

        config_path = Path(config_path)

        for config_file in config_path.glob("*.json"):
            with open(config_file, "r", encoding="utf-8") as in_file:
                try:
                    file_data = json.load(in_file)
                    config_model = PluginConfig(**file_data)
                    if config_model.name:
                        self.configs[config_model.name] = config_model
                    else:
                        self.configs[config_file.name] = config_model
                except (ValidationError, json.JSONDecodeError):
                    pass
