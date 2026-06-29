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

import re
from typing import Mapping, Optional

PORT_TOKEN_RE = re.compile(r"^(?:Eth)?(\d+(?:/\d+)*)$", re.IGNORECASE)
SAFE_ETH_PORT_RE = re.compile(r"^Eth\d+(?:/\d+)*$", re.IGNORECASE)


def normalize_port_token(port: str) -> Optional[str]:
    """Return the canonical port key (slash-separated indices, no Eth prefix)."""
    match = PORT_TOKEN_RE.match(port.strip())
    if not match:
        return None
    return match.group(1)


def to_eth_port_name(port: str) -> Optional[str]:
    """Return a validated Eth… port name safe for CLI interpolation."""
    canonical = normalize_port_token(port)
    if canonical is None:
        return None
    eth_name = f"Eth{canonical}"
    if not SAFE_ETH_PORT_RE.match(eth_name):
        return None
    return eth_name


def resolve_detail_port_names(
    ports_arg: list[str],
    interface_status: Optional[Mapping[str, object]] = None,
) -> tuple[Optional[list[str]], Optional[str]]:
    """Map collection/analysis port tokens to Eth… names from interface status when possible.

    Args:
        ports_arg: Port identifiers such as ``1/1/1`` or ``Eth1/1/1``.
        interface_status: Optional ``show interface status`` map keyed by Eth… names.

    Returns:
        Tuple of (resolved Eth port names, invalid token). On success the invalid token is None.
    """
    canonical_ports: list[str] = []
    for port in ports_arg:
        canonical = normalize_port_token(port)
        if canonical is None:
            return None, port
        canonical_ports.append(canonical)

    status_by_canonical: dict[str, str] = {}
    if interface_status:
        for name in interface_status:
            canonical = normalize_port_token(name)
            if canonical:
                status_by_canonical[canonical] = name

    detail_names: list[str] = []
    for canonical in canonical_ports:
        eth_name = status_by_canonical.get(canonical) or to_eth_port_name(canonical)
        if eth_name is None:
            return None, canonical
        detail_names.append(eth_name)
    return detail_names, None
