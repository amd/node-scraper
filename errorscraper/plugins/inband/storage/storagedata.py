from pydantic import BaseModel, field_serializer

from errorscraper.models import DataModel
from errorscraper.utils import bytes_to_human_readable


class DeviceStorageData(BaseModel):
    total: int
    free: int
    used: int
    percent: float

    @field_serializer("total")
    def serialize_total(self, total: int, _info) -> str:
        return bytes_to_human_readable(total)

    @field_serializer("free")
    def serialize_free(self, free: int, _info) -> str:
        return bytes_to_human_readable(free)

    @field_serializer("used")
    def serialize_used(self, used: int, _info) -> str:
        return bytes_to_human_readable(used)

    @field_serializer("percent")
    def serialize_percent(self, percent: float, _info) -> str:
        return f"{percent}%"


class StorageDataModel(DataModel):
    storage_data: dict[str, DeviceStorageData]
