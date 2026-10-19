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
import io
import os
import tarfile
from typing import Any, TypeVar, Union

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from nodescraper.utils import get_unique_filename

TDataModel = TypeVar("TDataModel", bound="DataModel")


class FileModel(BaseModel):
    """Binary file payload. JSON uses URL-safe base64 for ``file_contents``."""

    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    file_contents: bytes
    file_name: str

    @field_validator("file_contents", mode="before")
    @classmethod
    def file_contents_conformer(
        cls, value: Union[io.BytesIO, str, bytes], info: ValidationInfo
    ) -> Union[str, bytes]:
        if isinstance(value, io.BytesIO):
            return value.getvalue()
        if isinstance(value, str) and info.mode != "json":
            # Constructor/Python input is text.
            return value.encode("utf-8")
        # JSON strings stay base64 for val_json_bytes.
        return value

    def log_model(self, log_path: str) -> None:
        """Log data model to a file

        Args:
            log_path (str): log path
        """
        log_name = os.path.join(log_path, self.file_name)
        with open(log_name, "wb") as log_file:
            log_file.write(self.file_contents)

    def file_contents_str(self) -> None:
        return self.file_contents.decode("utf-8")


class DataModel(BaseModel):
    """Base class for data model, used to define structure of data collected from the system"""

    def log_model(self, log_path: str):
        """Log data model to a file

        Args:
            log_path (str): log path
        """
        log_name = os.path.join(
            log_path,
            get_unique_filename(log_path, f"{self.__class__.__name__.lower()}.json"),
        )

        # Write binary FileModel payloads as files; keep them in JSON as base64.
        for key in self.__class__.model_fields:
            data = getattr(self, key)
            if isinstance(data, FileModel):
                data.log_model(log_path)
            elif (
                isinstance(data, list)
                and data
                and all(isinstance(item, FileModel) for item in data)
            ):
                for item in data:
                    item.log_model(log_path)

        with open(log_name, "w", encoding="utf-8") as log_file:
            log_file.write(self.model_dump_json(indent=2))

    def merge_data(self, input_data: "DataModel") -> None:
        """Merge data into current data"""
        pass

    @classmethod
    def import_model(cls: type[TDataModel], model_input: Union[dict[str, Any], str]) -> TDataModel:
        """import a data model
        if the input is a string attempt to read data from file using the string as a file name
        if input is a dict, pass key value pairs directly to init function


        Args:
            cls (type[DataModel]): Data model class
            model_input (Union[dict[str, Any], str]): model data input

        Raises:
            ValueError: if model_input has an invalid type

        Returns:
            DataModel: instance of the data model
        """

        if isinstance(model_input, dict):
            return cls(**model_input)

        if isinstance(model_input, str):
            # Build from folder if supported
            if os.path.isdir(model_input):
                return cls.build_from_folder(model_input)
            # Build from tarfile if supported
            elif tarfile.is_tarfile(model_input):
                return cls.build_from_tar(model_input)
            # Build from json file
            else:
                with open(model_input, "r", encoding="utf-8") as input_file:
                    return cls.model_validate_json(input_file.read())

        raise ValueError("Invalid input for model data")

    @classmethod
    def build_from_tar(cls: type[TDataModel], tar_path: str) -> TDataModel:
        """Placeholder for building data model from tarfile.

        Intended for use with models that contains multiple FileModel attributes, and when collected they
        are in a tarfile. This is left blank if the model requires this then this function should be implemented.

        Parameters
        ----------
        cls : type[DataModelGeneric@build_from_tar]
            A DataModel class
        tar_path : str
            A path to a folder containing the data in format .tar.xz

        Returns
        -------
        DataModelGeneric@build_from_tar
            A datamodel object of type cls
        """
        raise NotImplementedError("Model does not support construction from tar")

    @classmethod
    def build_from_folder(cls: type[TDataModel], folder_path: str) -> TDataModel:
        """Placeholder for building data model from folder.

        Intended for use with models that contains multiple FileModel attributes. This is left blank
        if that model requires this then this function should be implemented.

        Parameters
        ----------
        cls : type[DataModelGeneric@build_from_folder]
            A DataModel class
        folder_path : str
            A path to a folder containing the data in format .tar.xz

        Returns
        -------
        DataModelGeneric@build_from_folder
            A datamodel object of type cls
        """
        raise NotImplementedError("Model does not support construction from folder")
