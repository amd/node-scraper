from pydantic import BaseModel


class ProcessAnalyzerArgs(BaseModel):
    max_kfd_processes: int = 0
    max_cpu_usage: int = 20
