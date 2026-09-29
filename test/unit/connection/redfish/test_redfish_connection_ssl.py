###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.connection.redfish import RedfishConnection


def test_verify_ssl_false_disables_trust_env() -> None:
    conn = RedfishConnection(
        base_url="https://bmc.example",
        username="u",
        password="p",
        verify_ssl=False,
        use_session_auth=False,
    )
    with patch(
        "nodescraper.connection.redfish.redfish_connection.requests.Session"
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        session = conn._ensure_session()

    assert session is mock_session
    assert mock_session.verify is False
    assert mock_session.trust_env is False


@pytest.mark.parametrize("env_var", ["REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"])
def test_verify_ssl_false_passes_verify_on_login(
    env_var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(env_var, "/etc/ssl/certs/ca-bundle.crt")
    conn = RedfishConnection(
        base_url="https://bmc.example",
        username="u",
        password="p",
        verify_ssl=False,
    )
    with patch(
        "nodescraper.connection.redfish.redfish_connection.requests.Session"
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.headers = {
            "X-Auth-Token": "token",
            "Location": "/redfish/v1/SessionService/Sessions/1",
        }
        mock_session.post.return_value = mock_response
        mock_session_cls.return_value = mock_session
        conn._ensure_session()

    mock_session.post.assert_called_once()
    assert mock_session.verify is False
    assert mock_session.trust_env is False
