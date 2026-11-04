#!/usr/bin/env python3
"""Download external rule lists into rule/ext as Loon remote-rule syntax.

Loon remote lists use ``TYPE,value`` or ``TYPE,value,no-resolve`` and do not
carry a policy. Policy and tag live on the ``[Remote Rule]`` line in
config/config.lcf. IP-CIDR and IP-CIDR6 lines in ChinaIP.list and Lan.list
always get ``no-resolve``.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "rule" / "ext"

ALLOWED_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "USER-AGENT",
    "URL-REGEX",
    "IP-CIDR",
    "IP-CIDR6",
    "GEOIP",
    "IP-ASN",
    "DST-PORT",
}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN"}
POLICY_TOKENS = {
    "DIRECT",
    "PROXY",
    "REJECT",
    "REJECT-DROP",
    "REJECT-IMG",
    "REJECT-DICT",
    "REJECT-ARRAY",
}
JOIN_VALUE_TYPES = {"URL-REGEX", "USER-AGENT"}

# name, raw URL, SPDX id, force no-resolve on IP-CIDR/IP-CIDR6
SOURCES: list[tuple[str, str, str, bool]] = [
    (
        "Netflix.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Netflix/Netflix.list",
        "GPL-2.0",
        False,
    ),
    (
        "Disney.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Disney/Disney.list",
        "GPL-2.0",
        False,
    ),
    (
        "YouTube.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/YouTube/YouTube.list",
        "GPL-2.0",
        False,
    ),
    (
        "Discord.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Discord/Discord.list",
        "GPL-2.0",
        False,
    ),
    (
        "OneDrive.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/OneDrive/OneDrive.list",
        "GPL-2.0",
        False,
    ),
    (
        "SteamCN.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/SteamCN/SteamCN.list",
        "GPL-2.0",
        False,
    ),
    (
        "Crypto.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Crypto/Crypto.list",
        "GPL-2.0",
        False,
    ),
    (
        "Lan.list",
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Lan/Lan.list",
        "GPL-2.0",
        True,
    ),
    (
        "ChinaDomain.list",
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/direct.txt",
        "GPL-3.0",
        False,
    ),
    (
        "ChinaIP.list",
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/cncidr.txt",
        "GPL-3.0",
        True,
    ),
    (
        "Proxy.list",
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/proxy.txt",
        "GPL-3.0",
        False,
    ),
]


def download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Proxy_rule-sync-ext-rules"})
    last_error: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
    raise RuntimeError(f"download failed: {url}: {last_error}")


def transform_line(line: str, force_no_resolve: bool) -> str | None:
    """Return a Loon rule line, ``""`` for a kept blank/comment, or None to drop."""
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith(";"):
        return stripped
    parts = [part.strip() for part in stripped.split(",")]
    rule_type = parts[0]
    if rule_type not in ALLOWED_TYPES:
        return None
    rest = parts[1:]
    no_resolve = False
    while rest:
        tail = rest[-1]
        if tail == "no-resolve":
            no_resolve = True
            rest.pop()
            continue
        if tail in POLICY_TOKENS:
            rest.pop()
            continue
        break
    if not rest:
        return None
    if rule_type in JOIN_VALUE_TYPES:
        value = ",".join(rest)
    elif len(rest) == 1:
        value = rest[0]
    else:
        return None
    if not value:
        return None
    if force_no_resolve and rule_type in {"IP-CIDR", "IP-CIDR6"}:
        no_resolve = True
    if no_resolve and rule_type not in IP_TYPES:
        no_resolve = False
    if no_resolve:
        return f"{rule_type},{value},no-resolve"
    return f"{rule_type},{value}"


def transform(text: str, force_no_resolve: bool) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    for raw in text.splitlines():
        result = transform_line(raw, force_no_resolve)
        if result is None:
            dropped.append(raw.strip())
            continue
        kept.append(result)
    while kept and kept[-1] == "":
        kept.pop()
    return kept, dropped


def header(url: str, license_id: str, fetched: str) -> list[str]:
    return [
        f"# Source: {url}",
        f"# Upstream-License: {license_id}",
        f"# Fetched: {fetched}",
        "",
    ]


def existing_body(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if (
        len(lines) >= 4
        and lines[0].startswith("# Source: ")
        and lines[1].startswith("# Upstream-License: ")
        and lines[2].startswith("# Fetched: ")
        and lines[3] == ""
    ):
        return lines[4:]
    return None


def write_list(name: str, url: str, license_id: str, force_no_resolve: bool, raw: str, fetched: str) -> str:
    body, dropped = transform(raw, force_no_resolve)
    path = DEST / name
    previous = existing_body(path)
    if previous == body:
        print(f"{name}: unchanged ({len(body)} lines)")
        return "unchanged"
    path.write_text("\n".join(header(url, license_id, fetched) + body) + "\n", encoding="utf-8")
    print(f"{name}: wrote {len(body)} lines, dropped {len(dropped)}")
    for line in dropped[:20]:
        print(f"  drop {line}", file=sys.stderr)
    if len(dropped) > 20:
        print(f"  ... {len(dropped) - 20} more", file=sys.stderr)
    return "updated"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    fetched = date.today().isoformat()
    downloaded: list[tuple[str, str, str, bool, str]] = []
    for name, url, license_id, force_no_resolve in SOURCES:
        print(f"fetch {url}")
        downloaded.append((name, url, license_id, force_no_resolve, download(url)))
    for name, url, license_id, force_no_resolve, raw in downloaded:
        write_list(name, url, license_id, force_no_resolve, raw, fetched)


if __name__ == "__main__":
    main()
