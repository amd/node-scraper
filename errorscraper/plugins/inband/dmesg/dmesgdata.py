import os
import re

from errorscraper.models import DataModel
from errorscraper.utils import get_unique_filename


class DmesgData(DataModel):
    """Data model for in band dmesg log"""

    dmesg_content: str

    @classmethod
    def get_new_dmesg_lines(cls, current_dmesg: str, new_dmesg: str) -> str:
        """Get new dmesg lines that are in one output but not another

        Args:
            current_dmesg (str): initial dmesg output
            new_dmesg (str): updated dmesg output

        Returns:
            str: lines that are at the end of new_dmesg but not current_dmesg
        """
        new_lines = []
        new_dmesg_lines = new_dmesg.splitlines()

        # reverse since any new lines will be at the end, so we want to start looking from there
        new_dmesg_lines.reverse()

        for line in new_dmesg_lines:
            date = re.search(r"(\d{4}-\d+-\d+T\d+:\d+:\d+),(\d+[+-]\d+:\d+)", line)
            if date and line in current_dmesg:
                # only break for lines with a date that already exist in current dmesg
                # lines with a date will be unique
                break

            new_lines.append(line)

        # put new lines back in correct order since we appended in reverse
        new_lines.reverse()

        return ("\n").join(new_lines)

    def merge_data(self, input_data: "DmesgData"):
        new_lines = self.get_new_dmesg_lines(input_data.dmesg_content, self.dmesg_content)
        merged_data = input_data.dmesg_content.strip() + f"\n{new_lines.strip()}"
        self.dmesg_content = merged_data

    def log_model(self, log_path: str):
        """Log data model to a file

        Args:
            log_path (str): log path
        """
        log_name = os.path.join(log_path, get_unique_filename(log_path, "dmesg.log"))
        with open(log_name, "w", encoding="utf-8") as log_file:
            log_file.write(self.dmesg_content)

    @classmethod
    def import_model(cls, model_input: dict | str) -> "DmesgData":
        """Load dmesg data

        Args:
            model_input (dict | str): dmesg file name or dmesg data dict

        Raises:
            ValueError: id model data has an invalid value

        Returns:
            DmesgDataModel: dmesg data model object
        """

        if isinstance(model_input, dict):
            return cls(**model_input)

        if isinstance(model_input, str):
            with open(model_input, "r", encoding="utf-8") as input_file:
                dmesg_data = input_file.read()

            return cls(dmesg_content=dmesg_data)

        raise ValueError("Invalid input for model data")
