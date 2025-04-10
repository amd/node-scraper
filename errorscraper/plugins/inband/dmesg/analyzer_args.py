from typing import Optional

from errorscraper.models import TimeRangeAnalyisArgs


class DmesgAnalyzerArgs(TimeRangeAnalyisArgs):
    check_unknown_dmesg_errors: Optional[bool] = True
    exclude_category: Optional[set[str]] = None
