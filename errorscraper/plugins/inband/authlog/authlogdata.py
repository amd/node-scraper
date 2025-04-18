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
