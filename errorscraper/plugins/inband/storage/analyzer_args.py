from pydantic import BaseModel


class StorageAnalyzerArgs(BaseModel):
    min_required_free_space: str = "50G"
