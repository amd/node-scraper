from typing import Generic

from errorscraper.connection.inband import InBandConnectionManager, SSHConnectionParams
from errorscraper.generictypes import TAnalyzeArg, TCollectArg, TDataModel
from errorscraper.interfaces import DataPlugin


class InBandDataPlugin(
    DataPlugin[InBandConnectionManager, SSHConnectionParams, TDataModel, TCollectArg, TAnalyzeArg],
    Generic[TDataModel, TCollectArg, TAnalyzeArg],
):
    """Base class for in band plugins"""

    CONNECTION_TYPE = InBandConnectionManager
