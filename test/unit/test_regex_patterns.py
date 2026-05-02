import re

from nodescraper import regex_patterns


def test_ipv4_pattern_matches():
    pat = regex_patterns.get_pattern("ipv4")
    compiled = re.compile(pat)
    assert compiled.search("address 192.0.2.1")


def test_mac_and_uuid_patterns_match():
    mac = regex_patterns.get_pattern("mac")
    uuid = regex_patterns.get_pattern("uuid")
    assert re.search(mac, "found MAC 00:1A:2B:3C:4D:5E")
    assert re.search(uuid, "id: 123e4567-e89b-12d3-a456-426655440000")


def test_build_error_regex_dicts_works():
    rules = regex_patterns.build_error_regex_dicts(["ipv4", "email"], message_template="got {name}")
    assert isinstance(rules, list) and len(rules) == 2
    assert all("regex" in r and "message" in r for r in rules)
