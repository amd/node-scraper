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
import json
import os
import tarfile
from typing import Any, TypeVar, Union

from pydantic import BaseModel, Field, field_validator

from nodescraper.utils import get_unique_filename

TDataModel = TypeVar("TDataModel", bound="DataModel")


class FileModel(BaseModel):
    """A file captured from the system.

    ``file_contents`` is excluded from model serialization (it may be binary); use
    ``to_file`` to write the raw bytes to disk.
    """

    file_contents: bytes = Field(default=b"", exclude=True)
    file_name: str

    @field_validator("file_contents", mode="before")
    @classmethod
    def file_contents_conformer(cls, value: Union[io.BytesIO, str, bytes]) -> bytes:
        if isinstance(value, io.BytesIO):
            return value.getvalue()
        if isinstance(value, str):
            return value.encode("utf-8")
        return value

    def to_file(self, log_path: str) -> None:
        """Write the raw file contents to ``log_path``/``file_name``

        Args:
            log_path (str): directory to write the file into

        Raises:
            ValueError: if ``file_name`` resolves to a location outside of ``log_path``
        """
        base_dir = os.path.realpath(log_path)
        log_name = os.path.realpath(os.path.join(base_dir, self.file_name))
        if os.path.commonpath([base_dir, log_name]) != base_dir or log_name == base_dir:
            raise ValueError(f"file_name {self.file_name!r} resolves outside of {log_path!r}")
        os.makedirs(os.path.dirname(log_name), exist_ok=True)
        with open(log_name, "wb") as log_file:
            log_file.write(self.file_contents)

    def log_model(self, log_path: str) -> None:
        """Alias for ``to_file``"""
        self.to_file(log_path)

    def file_contents_str(self) -> str:
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

        for key in self.__class__.model_fields:
            data = getattr(self, key)
            if isinstance(data, FileModel):
                data.to_file(log_path)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, FileModel):
                        item.to_file(log_path)

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
                    data = json.load(input_file)
                return cls(**data)

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
