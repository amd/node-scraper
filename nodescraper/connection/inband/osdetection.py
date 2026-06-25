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
import json
import re
from dataclasses import dataclass
from typing import Optional

from nodescraper.enums import OSFamily

from .inband import InBandConnection

ARISTA_VERSION_CMD = "show version | json | no-more"
DELL_VERSION_CMD = 'sonic-cli -c "show version | no-more"'

_DELL_VERSION_PATTERNS = (
    re.compile(r"SONiC Software Version:\s*(.+)", re.IGNORECASE),
    re.compile(r"SONiC OS Version:\s*(.+)", re.IGNORECASE),
)
_DELL_MODEL_PATTERNS = (
    re.compile(r"HwSKU:\s*(.+)", re.IGNORECASE),
    re.compile(r"Model Number:\s*(.+)", re.IGNORECASE),
    re.compile(r"Platform:\s*(.+)", re.IGNORECASE),
)


@dataclass(frozen=True)
class NetworkOsDetection:
    """Detected network operating system details."""

    os_family: OSFamily
    platform: str
    metadata: dict[str, str]


def _first_regex_match(patterns: tuple[re.Pattern[str], ...], text: str) -> Optional[str]:
    """Return the first captured group from the first matching regex pattern."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def parse_arista_version_output(stdout: str) -> Optional[NetworkOsDetection]:
    """Parse Arista EOS ``show version | json`` output into detection details.

    Args:
        stdout: Command stdout containing JSON version data.

    Returns:
        NetworkOsDetection when the output identifies an Arista device, else None.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    mfg_name = str(data.get("mfgName") or data.get("mfg_name") or "")
    if "arista" not in mfg_name.lower():
        return None

    metadata: dict[str, str] = {}
    version = data.get("version")
    if version:
        metadata["os_version"] = str(version)
    model_name = data.get("modelName") or data.get("model_name")
    if model_name:
        metadata["device_model"] = str(model_name)

    return NetworkOsDetection(
        os_family=OSFamily.EOS,
        platform="Arista EOS",
        metadata=metadata,
    )


def parse_dell_sonic_version_output(stdout: str) -> Optional[NetworkOsDetection]:
    """Parse Dell SONiC ``show version`` text output into detection details.

    Args:
        stdout: Command stdout containing version text.

    Returns:
        NetworkOsDetection when the output identifies a Dell SONiC device, else None.
    """
    lowered = stdout.lower()
    if not all(marker in lowered for marker in ("dell", "sonic")):
        return None

    metadata: dict[str, str] = {}
    version = _first_regex_match(_DELL_VERSION_PATTERNS, stdout)
    if version:
        metadata["os_version"] = version
    model = _first_regex_match(_DELL_MODEL_PATTERNS, stdout)
    if model:
        metadata["device_model"] = model

    return NetworkOsDetection(
        os_family=OSFamily.SONIC,
        platform="Dell SONiC",
        metadata=metadata,
    )


def detect_network_os(connection: InBandConnection) -> Optional[NetworkOsDetection]:
    """Probe a network device for Arista EOS or Dell SONiC after uname fails.

    Args:
        connection: Active in-band connection to the target device.

    Returns:
        NetworkOsDetection when a supported network OS is identified, else None.
    """
    arista_res = connection.run_command(ARISTA_VERSION_CMD, timeout=30)
    if arista_res.exit_code == 0:
        detection = parse_arista_version_output(arista_res.stdout)
        if detection is not None:
            return detection

    dell_res = connection.run_command(DELL_VERSION_CMD, timeout=30)
    if dell_res.exit_code == 0:
        detection = parse_dell_sonic_version_output(dell_res.stdout)
        if detection is not None:
            return detection

    return None
