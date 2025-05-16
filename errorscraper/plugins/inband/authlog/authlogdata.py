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

from errorscraper.models import DataModel
from errorscraper.utils import get_unique_filename


class AuthLogDataModel(DataModel):
    """Data model for in band auth.log"""

    log_content: str

    def log_model(self, log_path: str):
        """Log data model to a file

        Args:
            log_path (str): log path
        """
        log_name = os.path.join(log_path, get_unique_filename(log_path, "auth.log"))
        with open(log_name, "w", encoding="utf-8") as log_file:
            log_file.write(self.log_content)

    @classmethod
    def import_model(cls, model_input: dict | str) -> "AuthLogDataModel":
        """Load auth.log data

        Args:
            model_input (dict | str): auth.log file name or auth.log data dict

        Raises:
            ValueError: id model data has an invalid value

        Returns:
            AuthLogDataModel: auth.log data model object
        """

        if isinstance(model_input, dict):
            return cls(**model_input)

        if isinstance(model_input, str):
            with open(model_input, "r", encoding="utf-8") as input_file:
                log_data = input_file.read()

            return cls(log_content=log_data)

        raise ValueError("Invalid input for model data")
