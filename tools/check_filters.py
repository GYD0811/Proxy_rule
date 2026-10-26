#!/usr/bin/env python3
"""Check Loon Remote Filter regexes and Proxy Group references.

Reads config/config.lcf and matches a generated sample of the subscription
node names. Region totals follow the real subscription: US 29, JP 19, SG 17,
TW 3. Low-rate and dedicated counts describe this sample only.

Loon NameRegex uses ICU (NSRegularExpression). The patterns stick to (?i),
lookahead, and character classes, which ICU and Python re both support.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "config.lcf"

REGION_FILTER = {
    "US": "US_Filter",
    "JP": "JP_Filter",
    "SG": "SG_Filter",
    "TW": "TW_Filter",
}
EXPECTED_REGION_TOTALS = {"US": 29, "JP": 19, "SG": 17, "TW": 3}

# template, count, region, low-rate (0.1x), dedicated (专线)
PATTERNS = [
    ("🇺🇸美国{n}-0.1倍 | 电信联通移动推荐", 8, "US", True, False),
    ("🇺🇸美国圣何塞{n}-0.1倍", 5, "US", True, False),
    ("🇺🇸美国洛杉矶{n}-0.1倍", 5, "US", True, False),
    ("🇺🇸美国{n} | 合适下载使用-0.1倍", 4, "US", True, False),
    ("🇺🇸美国圣何塞{n} | 三网推荐", 4, "US", False, False),
    ("🇺🇸美国洛杉矶{n} | 三网推荐", 3, "US", False, False),
    ("🇯🇵日本东京{n}-0.1倍 | 电信联通推荐", 8, "JP", True, False),
    ("🇯🇵日本东京{n}-0.1倍 | 高速专线推荐", 6, "JP", True, True),
    ("🇯🇵AWS日本{n} | 电信移动联通推荐", 5, "JP", False, False),
    ("🇸🇬新加坡{n} | 电信联通推荐", 4, "SG", False, False),
    ("🇸🇬新加坡{n}-0.1倍 | 电信联通推荐", 5, "SG", True, False),
    ("🇸🇬AWS新加坡{n} | 电信移动联通推荐", 3, "SG", False, False),
    ("🇸🇬新加坡 | 高速专线-hy{n}", 2, "SG", False, True),
    ("🇸🇬新加坡{n} | 高速专线-hy{n}", 3, "SG", False, True),
    ("🇹🇼台湾 | 避免晚高峰使用", 1, "TW", False, False),
    ("🇹🇼台湾{n} | 避免晚高峰使用", 2, "TW", False, False),
]

INFO_LINES = [
    "剩余流量：1.2 TB",
    "套餐到期：长期有效",
    "官网：https://example.com",
    "到期时间：长期有效",
    "流量：剩余 1.2TB",
    "流量重置：每月1日",
    "官网：日本",
    "剩余流量：美国-0.1倍专线",
]

# Real-looking names that must not enter the four region filters.
STRAY_REGIONS = [
    "🇭🇰香港1 | 电信推荐",
    "🇰🇷韩国首尔1",
    "🇬🇧英国伦敦1",
    "🇩🇪德国法兰克福1",
]

DIRECT_GROUPS = {
    "微软服务",
    "Apple",
    "Speedtest",
    "游戏平台",
    "Direct",
    "BiliBili",
    "抖音",
    "内网段【默认绕过】",
}
AI_POLICIES = ["美国", "美国自动", "日本自动", "新加坡自动", "日本", "新加坡"]
STANDARD_POLICIES = [
    "美国自动",
    "日本自动",
    "新加坡自动",
    "台湾自动",
    "美国",
    "日本",
    "新加坡",
    "台湾",
    "省流量",
    "专线",
]
BUSINESS_GROUPS = [
    "兜底",
    "AI",
    "常用论坛",
    "Leo",
    "谷歌服务",
    "微软服务",
    "PayPal",
    "Spotify",
    "Telegram",
    "TikTok",
    "X【Twitter】",
    "流媒体",
    "Apple",
    "Speedtest",
    "游戏平台",
    "Direct",
    "BiliBili",
    "抖音",
    "内网段【默认绕过】",
]
REMOVED_FILTERS = ("HK_Filter", "KR_Filter", "EU_Filter")
BUILTIN = {"DIRECT", "REJECT", "REJECT-DROP", "REJECT-IMG", "REJECT-DICT", "REJECT-ARRAY", "PROXY"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^\[(.+)\]\s*$", line)
        if header:
            current = header.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def parse_filters(lines: list[str]) -> dict[str, re.Pattern[str]]:
    filters: dict[str, re.Pattern[str]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(
            r'^(\S+)\s*=\s*NameRegex\s*,\s*FilterKey\s*=\s*"(.*)"\s*$',
            line,
        )
        if not match:
            fail(f"unrecognized Remote Filter line: {line}")
        name, pattern = match.group(1), match.group(2)
        if name in filters:
            fail(f"duplicate filter: {name}")
        try:
            filters[name] = re.compile(pattern)
        except re.error as exc:
            fail(f"{name} regex does not compile: {exc}")
    return filters


def parse_groups(lines: list[str]) -> dict[str, tuple[str, list[str], dict[str, str]]]:
    groups: dict[str, tuple[str, list[str], dict[str, str]]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(.+?)\s*=\s*(select|url-test)\s*,(.*)$", line)
        if not match:
            fail(f"unrecognized Proxy Group line: {line}")
        name, kind, body = match.group(1), match.group(2), match.group(3)
        if name in groups:
            fail(f"duplicate group: {name}")
        policies: list[str] = []
        params: dict[str, str] = {}
        for part in body.split(","):
            part = part.strip()
            if not part:
                fail(f"empty member in group {name}")
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
            else:
                policies.append(part)
        groups[name] = (kind, policies, params)
    return groups


def expand(template: str, count: int) -> list[str]:
    if "{n}" not in template:
        if count != 1:
            fail(f"template without {{n}} must have count 1: {template}")
        return [template]
    return [template.format(n=i) for i in range(1, count + 1)]


def build_nodes() -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []
    for template, count, region, low, dedicated in PATTERNS:
        for name in expand(template, count):
            nodes.append(
                {
                    "name": name,
                    "region": region,
                    "low": low,
                    "dedicated": dedicated,
                    "pattern": template,
                }
            )
    names = [node["name"] for node in nodes]
    if len(names) != len(set(names)):
        fail("generated node names are not unique")
    return nodes


def matched(filters: dict[str, re.Pattern[str]], name: str) -> list[str]:
    return [key for key, pattern in filters.items() if pattern.fullmatch(name)]


def check_nodes(filters: dict[str, re.Pattern[str]], nodes: list[dict[str, object]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    region_counts: Counter[str] = Counter()
    for node in nodes:
        name = str(node["name"])
        hits = matched(filters, name)
        for key in hits:
            counts[key] += 1
        regions = [region for region, key in REGION_FILTER.items() if key in hits]
        if regions != [node["region"]]:
            fail(f"{name} regions {regions}, expected {[node['region']]}")
        region_counts[str(node["region"])] += 1
        if ("ALL_Filter" in hits) is False:
            fail(f"real node missed by ALL_Filter: {name}")
        if ("省流量_Filter" in hits) != bool(node["low"]):
            fail(f"省流量 mismatch: {name} -> {hits}")
        if ("专线_Filter" in hits) != bool(node["dedicated"]):
            fail(f"专线 mismatch: {name} -> {hits}")
        if node["low"] and "-0.1倍" not in name:
            fail(f"low-rate sample missing -0.1倍: {name}")
        if node["dedicated"] and "专线" not in name:
            fail(f"dedicated sample missing 专线: {name}")

    if region_counts != Counter(EXPECTED_REGION_TOTALS):
        fail(f"region totals {dict(region_counts)} != {EXPECTED_REGION_TOTALS}")
    if sum(region_counts.values()) != 68 or counts["ALL_Filter"] != 68:
        fail(f"ALL count {counts['ALL_Filter']} with regions {dict(region_counts)}")
    expected_low = sum(1 for node in nodes if node["low"])
    expected_dedicated = sum(1 for node in nodes if node["dedicated"])
    if counts["省流量_Filter"] != expected_low:
        fail(f"省流量 count {counts['省流量_Filter']} != {expected_low}")
    if counts["专线_Filter"] != expected_dedicated:
        fail(f"专线 count {counts['专线_Filter']} != {expected_dedicated}")
    return counts


def check_rejected(filters: dict[str, re.Pattern[str]]) -> None:
    for name in INFO_LINES:
        hits = matched(filters, name)
        if hits:
            fail(f"info line entered {hits}: {name}")
    for name in STRAY_REGIONS:
        hits = matched(filters, name)
        if hits != ["ALL_Filter"]:
            fail(f"stray region node should match only ALL_Filter, got {hits}: {name}")
    negatives = {
        "🇺🇸美国1-10.1倍 | 电信联通移动推荐": {"ALL_Filter", "US_Filter"},
        "🇺🇸美国1-0.15倍 | 电信联通移动推荐": {"ALL_Filter", "US_Filter"},
        "🇺🇸美国10-0.1倍 | 电信联通移动推荐": {"ALL_Filter", "US_Filter", "省流量_Filter"},
        "游戏平台节点": {"ALL_Filter"},
        "斜坡节点": {"ALL_Filter"},
        "美女节点": {"ALL_Filter"},
        "台灣1 | 避免晚高峰使用": {"ALL_Filter", "TW_Filter"},
        "Japan Tokyo 1": {"ALL_Filter", "JP_Filter"},
        "singapore 1": {"ALL_Filter", "SG_Filter"},
        "UNITED STATES 1": {"ALL_Filter", "US_Filter"},
        "Taiwan 1": {"ALL_Filter", "TW_Filter"},
        "🇯🇵AWS日本9 | 电信移动联通推荐": {"ALL_Filter", "JP_Filter"},
        "🇸🇬AWS新加坡9 | 电信移动联通推荐": {"ALL_Filter", "SG_Filter"},
    }
    for name, expected in negatives.items():
        hits = set(matched(filters, name))
        if hits != expected:
            fail(f"{name} matched {sorted(hits)}, expected {sorted(expected)}")


def check_groups(
    text: str,
    filters: dict[str, re.Pattern[str]],
    groups: dict[str, tuple[str, list[str], dict[str, str]]],
) -> None:
    for removed in REMOVED_FILTERS:
        if removed in text:
            fail(f"{removed} is still referenced")
    for token in ("香港", "韩国", "欧洲", "HK_Filter", "KR_Filter", "EU_Filter"):
        if token in text:
            fail(f"removed region token still present: {token}")

    expected_filters = {
        "ALL_Filter",
        "US_Filter",
        "JP_Filter",
        "SG_Filter",
        "TW_Filter",
        "省流量_Filter",
        "专线_Filter",
        "Gemini_Filter",
    }
    if set(filters) != expected_filters:
        fail(f"filter set {set(filters)} != {expected_filters}")

    auto = {
        "美国自动": "US_Filter",
        "日本自动": "JP_Filter",
        "新加坡自动": "SG_Filter",
        "台湾自动": "TW_Filter",
    }
    manual = {
        "美国": "US_Filter",
        "日本": "JP_Filter",
        "新加坡": "SG_Filter",
        "台湾": "TW_Filter",
        "省流量": "省流量_Filter",
        "专线": "专线_Filter",
        "Gemini": "Gemini_Filter",
    }
    for name, filter_name in auto.items():
        kind, policies, params = groups[name]
        if kind != "url-test" or policies != [filter_name]:
            fail(f"{name} should url-test only {filter_name}, got {kind} {policies}")
        if params != {
            "url": "http://cp.cloudflare.com/generate_204",
            "interval": "600",
            "tolerance": "100",
        }:
            fail(f"{name} url-test params {params}")
        if any(policy in groups for policy in policies):
            fail(f"{name} nests a policy group")
    for name, filter_name in manual.items():
        kind, policies, params = groups[name]
        if kind != "select" or policies != [filter_name] or params:
            fail(f"{name} should select only {filter_name}, got {kind} {policies} {params}")

    if [name for name in groups if name not in BUSINESS_GROUPS and name not in auto and name not in manual]:
        fail(f"unexpected groups: {list(groups)}")
    if set(BUSINESS_GROUPS) - set(groups):
        fail(f"missing business groups: {set(BUSINESS_GROUPS) - set(groups)}")

    for name in BUSINESS_GROUPS:
        kind, policies, _params = groups[name]
        if kind != "select":
            fail(f"{name} should be select")
        if name == "AI":
            if policies != AI_POLICIES or "谷歌服务" in policies:
                fail(f"AI policies {policies}")
            continue
        if name == "谷歌服务":
            expected = ["Gemini", "AI"] + STANDARD_POLICIES
            if policies != expected:
                fail(f"谷歌服务 policies {policies}")
            continue
        expected = (["DIRECT"] if name in DIRECT_GROUPS else []) + STANDARD_POLICIES
        if policies != expected:
            fail(f"{name} policies {policies}")
        if name in DIRECT_GROUPS and policies[0] != "DIRECT":
            fail(f"{name} must keep DIRECT first")
        if name not in DIRECT_GROUPS and "DIRECT" in policies:
            fail(f"{name} gained DIRECT")

    known = set(groups) | set(filters) | BUILTIN
    for name, (_kind, policies, _params) in groups.items():
        for policy in policies:
            if policy not in known:
                fail(f"{name} references unknown policy {policy}")

    if any("ALL_Filter" in groups[name][1] for name in groups):
        fail("business/region groups must not expand ALL_Filter directly")
    if groups["Gemini"][1] != ["Gemini_Filter"]:
        fail(f"Gemini group members {groups['Gemini'][1]}")
    if "谷歌服务" in groups["Gemini"][1] or "谷歌服务" in groups["AI"][1]:
        fail("Gemini or AI references 谷歌服务")
    if "Gemini" in groups["AI"][1] or "AI" in groups["Gemini"][1]:
        fail("AI and Gemini reference each other")

    def walk(name: str, seen: set[str]) -> None:
        if name in seen:
            fail(f"policy cycle at {name}: {seen}")
        if name not in groups:
            return
        nxt = seen | {name}
        for policy in groups[name][1]:
            walk(policy, nxt)

    walk("谷歌服务", set())
    walk("Gemini", set())
    walk("AI", set())

    sections = parse_sections(text)
    for line in sections.get("Remote Rule", []):
        policy = re.search(r"policy=([^,\s]+)", line)
        if not policy:
            continue
        target = policy.group(1)
        if target not in groups and target not in BUILTIN:
            fail(f"remote rule policy missing: {target}")
    rule_lines = [line.strip() for line in sections.get("Rule", [])]
    final_rows = [line for line in rule_lines if line.startswith("FINAL,")]
    if final_rows != ["FINAL,兜底"]:
        fail(f"FINAL rule changed: {final_rows}")
    final_at = rule_lines.index("FINAL,兜底")
    if final_at == 0 or rule_lines[final_at - 1] != "GEOIP,CN,DIRECT":
        fail("GEOIP,CN,DIRECT must be the line directly before FINAL,兜底")
    direct_lines = (ROOT / "rule" / "Direct.list").read_text(encoding="utf-8").splitlines()
    for domain in ("qpic.cn", "qlogo.cn"):
        if f"DOMAIN-SUFFIX,{domain}" not in direct_lines:
            fail(f"Direct.list missing DOMAIN-SUFFIX,{domain}")
    general = [
        line.strip()
        for line in sections.get("General", [])
        if line.strip() and not line.strip().startswith("#")
    ]
    geoip_url = "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/Country.mmdb"
    geoip_lines = [line for line in general if line.startswith("geoip-url")]
    if geoip_lines != [f"geoip-url = {geoip_url}"]:
        fail(f"expected exactly one geoip-url, got {geoip_lines}")
    remote = [line.strip() for line in sections.get("Remote Rule", []) if line.strip() and not line.strip().startswith("#")]

    def remote_index(filename: str) -> int:
        hits = [i for i, line in enumerate(remote) if f"/rule/{filename}.list" in line]
        if len(hits) != 1:
            fail(f"remote rule {filename}.list count {len(hits)}")
        return hits[0]

    gemini_at = remote_index("Gemini")
    if not (gemini_at < remote_index("AI") and gemini_at < remote_index("Google")):
        fail("Gemini.list must be listed before AI.list and Google.list")
    if "policy=Gemini" not in remote[gemini_at]:
        fail(f"Gemini remote rule policy {remote[gemini_at]}")


GEMINI_NODES = [
    "🇯🇵AWS日本01 | 电信移动联通推荐",
    "🇺🇸美国05-0.1倍 | 电信联通移动推荐",
    "🇺🇸美国06-0.1倍 | 电信联通移动推荐",
    "🇺🇸美国07-0.1倍 | 电信联通移动推荐",
    "🇺🇸美国圣何塞05-0.1倍",
    "🇺🇸美国圣何塞06-0.1倍",
    "🇺🇸美国圣何塞07-0.1倍",
    "🇺🇸美国圣何塞05 | 三网推荐",
    "🇺🇸美国圣何塞06 | 三网推荐",
    "🇺🇸美国圣何塞07 | 三网推荐",
]
GEMINI_REJECT = [
    "🇺🇸美国05 | 合适下载使用-0.01倍",
    "🇺🇸美国圣何塞04 | 三网推荐",
    "🇯🇵AWS日本10 | 电信移动联通推荐",
    "剩余流量：4.74 TB",
]
GEMINI_DOMAINS = [
    "DOMAIN,ai.google.dev",
    "DOMAIN,aistudio.google.com",
    "DOMAIN,alkalimakersuite-pa.clients6.google.com",
    "DOMAIN,generativelanguage.googleapis.com",
    "DOMAIN,makersuite.google.com",
    "DOMAIN-SUFFIX,bard.google.com",
    "DOMAIN-SUFFIX,deepmind.com",
    "DOMAIN-SUFFIX,deepmind.google",
    "DOMAIN-SUFFIX,gemini.google",
    "DOMAIN-SUFFIX,gemini.google.com",
    "DOMAIN-SUFFIX,generativeai.google",
    "DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com",
]


def check_gemini(filters: dict[str, re.Pattern[str]], sample_count: int) -> None:
    if sample_count != 0:
        fail(f"generated 68-node sample matched Gemini_Filter {sample_count} times")
    matched_names = []
    for name in GEMINI_NODES:
        hits = matched(filters, name)
        if "Gemini_Filter" not in hits:
            fail(f"Gemini node missed: {name} -> {hits}")
        if "ALL_Filter" not in hits:
            fail(f"Gemini node missed ALL_Filter: {name}")
        matched_names.append(name)
    if len(matched_names) != 10:
        fail(f"expected 10 Gemini nodes, got {len(matched_names)}")
    for name in GEMINI_REJECT:
        hits = matched(filters, name)
        if "Gemini_Filter" in hits:
            fail(f"non-Gemini name matched Gemini_Filter: {name} -> {hits}")
    if matched(filters, "剩余流量：4.74 TB"):
        fail("剩余流量：4.74 TB entered a filter")
    ai_text = (ROOT / "rule" / "AI.list").read_text(encoding="utf-8")
    gemini_text = (ROOT / "rule" / "Gemini.list").read_text(encoding="utf-8")
    for line in GEMINI_DOMAINS:
        if line not in gemini_text.splitlines():
            fail(f"Gemini.list missing {line}")
        if line in ai_text.splitlines():
            fail(f"AI.list still contains {line}")


def print_gemini(filters: dict[str, re.Pattern[str]]) -> None:
    print("Gemini 节点自测：10 个通过节点命中 Gemini_Filter，以下名称不命中。")
    print()
    print("| 节点 | Gemini_Filter |")
    print("| --- | --- |")
    for name in GEMINI_NODES:
        print(f"| `{name}` | 是 |")
    for name in GEMINI_REJECT:
        print(f"| `{name}` | 否 |")
    print()


def pattern_rows(nodes: list[dict[str, object]]) -> None:
    print("| 样例模式 | 数量 | 地区 | 省流量 | 专线 |")
    print("| --- | ---: | --- | --- | --- |")
    seen: list[str] = []
    for node in nodes:
        pattern = str(node["pattern"])
        if pattern in seen:
            continue
        seen.append(pattern)
        subset = [item for item in nodes if item["pattern"] == pattern]
        print(
            f"| `{pattern}` | {len(subset)} | {subset[0]['region']} | "
            f"{'是' if subset[0]['low'] else ''} | {'是' if subset[0]['dedicated'] else ''} |"
        )


def main() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    sections = parse_sections(text)
    filters = parse_filters(sections["Remote Filter"])
    groups = parse_groups(sections["Proxy Group"])
    nodes = build_nodes()
    counts = check_nodes(filters, nodes)
    check_rejected(filters)
    check_groups(text, filters, groups)
    check_gemini(filters, counts["Gemini_Filter"])

    print("样例节点 68，信息条目不进入任何筛选。")
    print()
    print("| 筛选 | 命中 |")
    print("| --- | ---: |")
    for name in [
        "ALL_Filter",
        "US_Filter",
        "JP_Filter",
        "SG_Filter",
        "TW_Filter",
        "省流量_Filter",
        "专线_Filter",
    ]:
        print(f"| {name} | {counts[name]} |")
    print()
    print(f"信息条目 {len(INFO_LINES)} 条，命中任何筛选的数量：0")
    print("每个真实节点恰好命中一个地区筛选。省流量 / 专线可与地区重叠。")
    print()
    pattern_rows(nodes)
    print()
    print_gemini(filters)
    print("check_filters: ok")


if __name__ == "__main__":
    main()
