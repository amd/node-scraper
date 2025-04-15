from pydantic import BaseModel


class MemoryAnalyzerArgs(BaseModel):
    ratio: float = 0.66
    memory_threshold: str = "30Gi"
