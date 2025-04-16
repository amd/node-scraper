from errorscraper.models import DataModel


class OsDataModel(DataModel):
    os_name: str
    os_version: str = ""
