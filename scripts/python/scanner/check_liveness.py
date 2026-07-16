#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from scripts.python.pipeline.liveness_api import check_liveness_via_api
from scripts.python.pipeline.liveness_browser import check_url_liveness_with_playwright, jittered_delay_ms


def build_liveness_checker(
    *,
    use_browser: bool = False,
    api_checker: Callable[[str], dict[str, str] | None] = check_liveness_via_api,
    browser_checker: Callable[[str], Awaitable[dict[str, str]]] | None = None,
) -> Callable[[str], dict[str, str] | None]:
    async_browser_checker = browser_checker or check_url_liveness_with_playwright

    def check(url: str) -> dict[str, str] | None:
        api_result = api_checker(url)
        if api_result is not None or not use_browser:
            return api_result
        return asyncio.run(async_browser_checker(url))

    return check


async def check_urls(
    urls: list[str],
    *,
    api_checker: Callable[[str], dict[str, str] | None] = check_liveness_via_api,
    browser_checker: Callable[[str], Awaitable[dict[str, str]]] | None = None,
    throttle_base_ms: int = 0,
) -> dict[str, Any]:
    active = expired = uncertain = via_api = 0
    results: list[dict[str, Any]] = []
    for idx, url in enumerate(urls):
        api_result = api_checker(url)
        used_api = api_result is not None
        if api_result:
            result = api_result
            via_api += 1
        elif browser_checker:
            result = await browser_checker(url)
            wait = jittered_delay_ms(throttle_base_ms) if idx < len(urls) - 1 else 0
            if wait:
                await asyncio.sleep(wait / 1000)
        else:
            result = {"result": "uncertain", "code": "no_browser_checker", "reason": "ATS API inconclusive and no browser checker provided"}
        if result["result"] == "active":
            active += 1
        elif result["result"] == "expired":
            expired += 1
        else:
            uncertain += 1
        results.append({"url": url, "viaApi": used_api, **result})
    return {"active": active, "expired": expired, "uncertain": uncertain, "viaApi": via_api, "results": results}


def parse_urls(args: argparse.Namespace) -> list[str]:
    if args.file:
        return [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
    return args.urls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether job posting URLs are still active.")
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--file")
    parser.add_argument("--throttle", nargs="?", const="5000", default="0")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    urls = parse_urls(args)
    if not urls:
        print("Usage: check_liveness.py <url1> [url2] ...")
        return 1
    summary = asyncio.run(check_urls(urls, throttle_base_ms=int(args.throttle or 0)))
    for item in summary["results"]:
        marker = {"active": "active", "expired": "expired", "uncertain": "uncertain"}[item["result"]]
        print(f"{marker:10} {'(api)' if item['viaApi'] else '     '} {item['url']}")
        if item["result"] != "active":
            print(f"           {item['reason']}")
    print(f"\nResults: {summary['active']} active  {summary['expired']} expired  {summary['uncertain']} uncertain  ({summary['viaApi']} via API, no browser)")
    return 1 if summary["expired"] or summary["uncertain"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
