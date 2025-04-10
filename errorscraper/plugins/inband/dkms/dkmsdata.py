from typing import Optional

from errorscraper.datamodel import DataModel


class DkmsDataModel(DataModel):
    status: Optional[str] = None
    version: Optional[str] = None
