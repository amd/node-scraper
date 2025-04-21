from errorscraper.base import InBandDataPlugin

from .last_collector import LastCollector
from .lastdata import LastDataModel


class LastPlugin(InBandDataPlugin[LastDataModel, None, None]):
    """Plugin for collection of last logged in users"""

    DATA_MODEL = LastDataModel

    COLLECTOR = LastCollector
