import re

from pydantic import field_validator

from errorscraper.models import DataModel


class RocmDataModel(DataModel):
    rocm_version: str

    @field_validator("rocm_version")
    @classmethod
    def validate_rocm_version(cls, rocm_version: str) -> str:

        if not bool(
            re.match(
                r"^(\d+(?:\.\d+){0,3})-(\d+)$",
                rocm_version,
            )
        ):
            raise ValueError(f"ROCm version has invalid format: {rocm_version}")

        return rocm_version
