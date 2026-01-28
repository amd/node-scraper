###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import re

from pydantic import BaseModel

from nodescraper.base.regexanalyzer import ErrorRegex, RegexAnalyzer
from nodescraper.enums import EventCategory, EventPriority
from nodescraper.models.datamodel import DataModel


class DummyData(DataModel):
    pass


class DummyArgs(BaseModel):
    pass


class TestRegexAnalyzer(RegexAnalyzer[DummyData, DummyArgs]):
    DATA_MODEL = DummyData

    ERROR_REGEX = [
        ErrorRegex(
            regex=re.compile(r"base error 1"),
            message="Base Error 1",
            event_category=EventCategory.SW_DRIVER,
        ),
        ErrorRegex(
            regex=re.compile(r"base error 2"),
            message="Base Error 2",
            event_category=EventCategory.OS,
            event_priority=EventPriority.WARNING,
        ),
    ]

    def analyze_data(self, data, args=None):
        pass


def test_convert_and_extend_with_none(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    result = analyzer._convert_and_extend_error_regex(None, base_regex)

    assert len(result) == 2
    assert result[0].message == "Base Error 1"
    assert result[1].message == "Base Error 2"


def test_convert_and_extend_with_empty_list(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    result = analyzer._convert_and_extend_error_regex([], base_regex)

    assert len(result) == 2
    assert result[0].message == "Base Error 1"
    assert result[1].message == "Base Error 2"


def test_convert_and_extend_with_error_regex_objects(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    custom_regex = [
        ErrorRegex(
            regex=re.compile(r"custom error 1"),
            message="Custom Error 1",
            event_category=EventCategory.RAS,
        ),
        ErrorRegex(
            regex=re.compile(r"custom error 2"),
            message="Custom Error 2",
            event_category=EventCategory.BIOS,
            event_priority=EventPriority.CRITICAL,
        ),
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(result) == 4
    assert result[0].message == "Custom Error 1"
    assert result[0].event_category == EventCategory.RAS
    assert result[0].event_priority == EventPriority.ERROR
    assert result[1].message == "Custom Error 2"
    assert result[1].event_category == EventCategory.BIOS
    assert result[1].event_priority == EventPriority.CRITICAL
    assert result[2].message == "Base Error 1"
    assert result[3].message == "Base Error 2"


def test_convert_and_extend_with_dict_format(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    custom_regex = [
        {
            "regex": r"custom dict error 1",
            "message": "Custom Dict Error 1",
            "event_category": "RAS",
        },
        {
            "regex": r"custom dict error 2",
            "message": "Custom Dict Error 2",
            "event_category": "IO",
            "event_priority": 2,
        },
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(result) == 4
    assert result[0].message == "Custom Dict Error 1"
    assert result[0].event_category == EventCategory.RAS
    assert result[0].event_priority == EventPriority.ERROR
    assert isinstance(result[0].regex, re.Pattern)
    assert result[1].message == "Custom Dict Error 2"
    assert result[1].event_category == EventCategory.IO
    assert result[1].event_priority == EventPriority.WARNING
    assert isinstance(result[1].regex, re.Pattern)
    assert result[2].message == "Base Error 1"
    assert result[3].message == "Base Error 2"


def test_convert_and_extend_with_mixed_formats(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    custom_regex = [
        ErrorRegex(
            regex=re.compile(r"error regex object"),
            message="Error Regex Object",
            event_category=EventCategory.NETWORK,
        ),
        {
            "regex": r"error dict object",
            "message": "Error Dict Object",
            "event_category": "SW_DRIVER",
            "event_priority": 4,
        },
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(result) == 4
    assert result[0].message == "Error Regex Object"
    assert result[0].event_category == EventCategory.NETWORK
    assert result[1].message == "Error Dict Object"
    assert result[1].event_category == EventCategory.SW_DRIVER
    assert result[1].event_priority == EventPriority.CRITICAL
    assert result[2].message == "Base Error 1"
    assert result[3].message == "Base Error 2"


def test_convert_and_extend_dict_without_optional_fields(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    custom_regex = [
        {
            "regex": r"minimal error",
            "message": "Minimal Error",
        }
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(result) == 3
    assert result[0].message == "Minimal Error"
    assert result[0].event_category == EventCategory.UNKNOWN
    assert result[0].event_priority == EventPriority.ERROR


def test_convert_and_extend_regex_patterns_work(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX

    custom_regex = [
        {
            "regex": r"test\s+error\s+\d+",
            "message": "Test Error Pattern",
            "event_category": "SW_DRIVER",
        }
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(result) == 3
    test_string_match = "test error 123"
    test_string_no_match = "test error abc"

    assert result[0].regex.search(test_string_match) is not None
    assert result[0].regex.search(test_string_no_match) is None


def test_convert_and_extend_preserves_base_regex(system_info):
    analyzer = TestRegexAnalyzer(system_info=system_info)
    base_regex = analyzer.ERROR_REGEX
    original_base_length = len(base_regex)

    custom_regex = [
        {
            "regex": r"custom error",
            "message": "Custom Error",
        }
    ]

    result = analyzer._convert_and_extend_error_regex(custom_regex, base_regex)

    assert len(base_regex) == original_base_length
    assert len(result) == original_base_length + 1
