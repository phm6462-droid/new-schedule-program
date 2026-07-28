#!/usr/bin/env python3
"""Meditong 근무표를 GitHub Pages용 data/*.html로 동기화합니다.

환경변수:
- SYNC_START_MONTH: 처음 동기화할 월. 기본값 2026-03
- SYNC_FUTURE_MONTHS: 현재 월 기준 몇 개월 뒤까지 확인할지. 기본값 1
- MEDITONG_COOKIE: 로그인이 필요한 경우 GitHub Secrets에 저장한 Cookie 전체 문자열
- MEDITONG_GROUP_NO: 그룹 번호. 기본값 5119
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

KST = timezone(timedelta(hours=9))
SOURCE_HOST = "https://gw.meditong.com"
SOURCE_PATH = "/bizwiz/schedule/rnw_workSchedule_my_new.asp"
DEFAULT_START_MONTH = "2026-03"


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def parse_month_key(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(20\d{2})-(0[1-9]|1[0-2])", value.strip())
    if not match:
        raise ValueError(f"월 형식이 올바르지 않습니다: {value!r}. 예: 2026-07")
    return int(match.group(1)), int(match.group(2))


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    zero_based = (year * 12 + (month - 1)) + delta
    return zero_based // 12, zero_based % 12 + 1


def iter_months(start_key: str, end_key: str) -> list[str]:
    sy, sm = parse_month_key(start_key)
    ey, em = parse_month_key(end_key)
    months: list[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(month_key(y, m))
        y, m = add_months(y, m, 1)
    return months


def source_url(ym: str) -> str:
    group_no = os.getenv("MEDITONG_GROUP_NO", "5119")
    query = urlencode(
        {
            "group_no": group_no,
            "strGBTopMenu": "",
            "LCode": "l_31_1_1",
            "viewmode": "a",
            "nDate": ym,
        }
    )
    return f"{SOURCE_HOST}{SOURCE_PATH}?{query}"


def decode_response(raw: bytes, headers: Message) -> str:
    content_type = headers.get("Content-Type", "")
    match = re.search(r"charset=([\w\-]+)", content_type, re.I)
    encodings = []
    if match:
        encodings.append(match.group(1))
    encodings.extend(["utf-8", "cp949", "euc-kr"])

    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_html(ym: str) -> str:
    url = source_url(ym)
    headers = {
        "User-Agent": "Mozilla/5.0 (GitHub Actions schedule sync)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    cookie = os.getenv("MEDITONG_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        return decode_response(raw, response.headers)


def html_to_text(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_schedule(html: str) -> tuple[bool, str]:
    lower = html.lower()
    text = html_to_text(html)

    if "<table" not in lower:
        return False, "HTML 표가 없습니다."
    if "로그인" in text and "근무표" not in text:
        return False, "로그인 화면으로 보입니다. MEDITONG_COOKIE Secret이 필요할 수 있습니다."
    if "근무표" not in text:
        return False, "근무표 문구를 찾지 못했습니다."

    day_numbers = len(re.findall(r"(?:^|\s)(?:[1-9]|[12]\d|3[01])(?:\s|$)", text))
    if day_numbers < 20:
        return False, "날짜 열을 충분히 찾지 못했습니다."

    return True, ""


def write_if_changed(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def build_manifest(now_iso: str, failed: list[dict[str, str]]) -> dict:
    html_files = sorted(DATA_DIR.glob("20??-??.html"))
    months = []
    for path in html_files:
        key = path.stem
        try:
            year, month = parse_month_key(key)
        except ValueError:
            continue
        stat = path.stat()
        file_updated = datetime.fromtimestamp(stat.st_mtime, tz=KST).isoformat(timespec="seconds")
        months.append(
            {
                "key": key,
                "label": f"{year}년 {month:02d}월",
                "url": f"data/{path.name}",
                "fileName": path.name,
                "sourceUrl": source_url(key),
                "updatedAt": file_updated,
            }
        )

    return {
        "updatedAt": now_iso,
        "source": {
            "baseUrl": f"{SOURCE_HOST}{SOURCE_PATH}?group_no={os.getenv('MEDITONG_GROUP_NO', '5119')}&strGBTopMenu=&LCode=l_31_1_1&viewmode=a&nDate={{ym}}",
        },
        "months": months,
        "failed": failed,
    }


def main() -> int:
    now = datetime.now(KST)
    start_key = os.getenv("SYNC_START_MONTH", DEFAULT_START_MONTH).strip() or DEFAULT_START_MONTH
    future_months = int(os.getenv("SYNC_FUTURE_MONTHS", "1"))
    end_year, end_month = add_months(now.year, now.month, future_months)
    end_key = month_key(end_year, end_month)

    target_months = iter_months(start_key, end_key)
    failed: list[dict[str, str]] = []

    print(f"동기화 대상: {', '.join(target_months)}")
    for ym in target_months:
        try:
            html = fetch_html(ym)
            ok, reason = looks_like_schedule(html)
            if not ok:
                failed.append({"key": ym, "reason": reason})
                print(f"SKIP {ym}: {reason}")
                continue

            changed = write_if_changed(DATA_DIR / f"{ym}.html", html)
            print(f"{'UPDATED' if changed else 'UNCHANGED'} {ym}")
        except HTTPError as exc:
            reason = f"HTTP {exc.code}"
            failed.append({"key": ym, "reason": reason})
            print(f"FAIL {ym}: {reason}", file=sys.stderr)
        except URLError as exc:
            reason = str(exc.reason)
            failed.append({"key": ym, "reason": reason})
            print(f"FAIL {ym}: {reason}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            reason = str(exc)
            failed.append({"key": ym, "reason": reason})
            print(f"FAIL {ym}: {reason}", file=sys.stderr)

    manifest = build_manifest(now.isoformat(timespec="seconds"), failed)
    write_if_changed(DATA_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    print(f"manifest months: {len(manifest['months'])}")
    if failed:
        print("failed:")
        for item in failed:
            print(f"- {item['key']}: {item['reason']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
