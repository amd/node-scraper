from errorscraper.models import DataModel


class MemoryDataModel(DataModel):
    mem_free: str
    mem_total: str
