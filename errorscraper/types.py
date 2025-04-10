from typing import Optional, TypeVar

from pydantic import BaseModel

from errorscraper.models import DataModel

TDataModel = TypeVar("TDataModel", bound="DataModel")
TCollectArg = TypeVar("TCollectArg", bound="Optional[BaseModel]")
TAnalyzeArg = TypeVar("TAnalyzeArg", bound="Optional[BaseModel]")
