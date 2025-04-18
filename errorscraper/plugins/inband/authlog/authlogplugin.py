from errorscraper.base import InBandDataPlugin

from .authlog_collector import AuthLogCollector
from .authlogdata import AuthLogDataModel


class AuthLogPlugin(InBandDataPlugin[AuthLogDataModel, None, None]):
    """Plugin for collection of authentication logs"""

    DATA_MODEL = AuthLogDataModel

    COLLECTOR = AuthLogCollector
