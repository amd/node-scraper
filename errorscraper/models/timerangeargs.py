import datetime
from typing import Optional

from pydantic import BaseModel


class TimeRangeAnalyisArgs(BaseModel):
    analysis_range_start: Optional[datetime.datetime] = None
    analysis_range_end: Optional[datetime.datetime] = None
