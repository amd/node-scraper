from typing import Optional

from errorscraper.models import DataModel


class ProcessDataModel(DataModel):
    kfd_process: Optional[int] = None
    cpu_usage: Optional[float] = None
    processes: Optional[list[tuple[str, str]]] = None
