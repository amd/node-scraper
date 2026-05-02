from nodescraper.models.systeminfo import SystemInfo
from nodescraper.plugins.regex_search.regex_search_analyzer import RegexSearchAnalyzer
from nodescraper.plugins.regex_search.regex_search_data import RegexSearchData
from nodescraper.plugins.regex_search.analyzer_args import RegexSearchAnalyzerArgs

from nodescraper import regex_patterns


def test_regex_search_analyzer_detects_ipv4():
    system_info = SystemInfo()
    analyzer = RegexSearchAnalyzer(system_info=system_info)

    # Content includes an ISO-like timestamp and an IPv4 address
    content = "2026-05-01T12:00:00,000+00:00 Something happened at 192.0.2.123\n"
    data = RegexSearchData(content=content, data_root="regex_search")

    args = {
        "error_regex": regex_patterns.build_error_regex_dicts(["ipv4"], message_template="Found {name}"),
        "num_timestamps": 2,
        "interval_to_collapse_event": 60,
    }

    result = analyzer.analyze_data(data, args)

    assert result is not None
    assert len(result.events) >= 1
    ev = result.events[0]
    # matched content should include the IPv4
    assert "192.0.2.123" in str(ev.data.get("match_content", ""))
