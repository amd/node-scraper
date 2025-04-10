from errorscraper.interfaces.inbanddataplugin import InBandDataPlugin

from .dimm_collector import DimmCollector
from .dimmdata import DimmDataModel


class DimmPlugin(InBandDataPlugin[DimmDataModel, None, None]):
    """Plugin for collection and analysis of BIOS data"""

    DATA_MODEL = DimmDataModel

    COLLECTOR = DimmCollector
