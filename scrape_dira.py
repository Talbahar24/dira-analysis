#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""משיכת כל ההגרלות הפתוחות מאתר דירה בהנחה — Playwright + API"""

import csv
import re
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

URL = "https://dira.moch.gov.il/ProjectsList"
API_BASE = "https://dira.moch.gov.il/api/Invoker"
OUTPUT = Path(__file__).parent / "dira_projects.csv"
PAGE_SIZE = 50
PROJECT_STATUS_OPEN = 4  # פתוח להרשמה

COLUMNS = [
    "מספר הגרלה",
    "סוג הגרלה",
    "זכאות",
    "סיום הרשמה",
    "יישוב",
    "קבלן",
    "דירות בהגרלה",
    "נרשמים בהגרלה",
    "מחיר למטר",
    "מענק",
    "הערות",
    "יחס נרשמים/דירות",
    "אחוז סיכוי משוער",
]


def parse_number(value):
    if not value:
        return 0
    s = re.sub(r"[,₪*%\s]", "", str(value))
    try:
        return float(s)
    except ValueError:
        return 0


def strip_html(text):
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def format_date(value):
    if not value:
        return ""
    return value.split("T")[0].replace("-", "/")


def api_url(page_number, is_init=False):
    params = (
        f"?firstApplicantIdentityNumber="
        f"&secondApplicantIdentityNumber="
        f"&ProjectStatus={PROJECT_STATUS_OPEN}"
        f"&Entitlement=1"
        f"&PageNumber={page_number}"
        f"&PageSize={PAGE_SIZE}"
        f"&IsInit={'true' if is_init else 'false'}"
        f"&"
    )
    return f"{API_BASE}?method=Projects&param={quote(params, safe='')}"


def item_to_record(item):
    flats = int(item.get("LotteryApparmentsNum") or item.get("TargetHousingUnits") or 0)
    registered = int(item.get("TotalSubscribers") or 0)
    notes = strip_html(item.get("Notes", ""))
    if len(notes) > 120:
        notes = notes[:117] + "..."

    record = {
        "מספר הגרלה": str(item.get("LotteryNumber", "")),
        "סוג הגרלה": str(item.get("LotteryType", "")),
        "זכאות": item.get("EntitlementDescription") or item.get("Entitlement", ""),
        "סיום הרשמה": format_date(item.get("ApplicationEndDate", "")),
        "יישוב": item.get("CityDescription", ""),
        "קבלן": item.get("ContractorDescription", ""),
        "דירות בהגרלה": str(flats),
        "נרשמים בהגרלה": str(registered),
        "מחיר למטר": f"₪{item['PricePerUnit']:,.2f}" if item.get("PricePerUnit") else "",
        "מענק": f"₪{item['GrantSize']:,.0f}" if item.get("GrantSize") else "₪0",
        "הערות": notes,
    }

    if flats > 0 and registered > 0:
        record["יחס נרשמים/דירות"] = f"{registered / flats:.2f}"
        record["אחוז סיכוי משוער"] = f"{(flats / registered) * 100:.2f}%"
    else:
        record["יחס נרשמים/דירות"] = ""
        record["אחוז סיכוי משוער"] = ""

    return record


def fetch_all_projects(request):
    all_items = []
    total = None
    page_number = 1

    while True:
        response = request.get(api_url(page_number, is_init=(page_number == 1)))
        if response.status != 200:
            raise RuntimeError(f"API נכשל בעמוד {page_number}: {response.status}")

        data = response.json()
        items = data.get("ProjectItems") or []
        all_items.extend(items)

        if total is None:
            total = data.get("NumOfRecords") or data.get("OpenLotteriesCount") or 0
            print(f"סה\"כ הגרלות פתוחות באתר: {total}")

        print(f"עמוד {page_number}: {len(items)} רשומות (מצטבר: {len(all_items)})")

        if len(all_items) >= total or not items:
            break
        page_number += 1

    return all_items, total


def scrape(headless=True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="he-IL",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        print("פותח את האתר לקבלת session...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        items, expected = fetch_all_projects(context.request)
        browser.close()

    records = [item_to_record(i) for i in items]
    records.sort(key=lambda r: parse_number(r.get("יחס נרשמים/דירות", 9999)))
    return records, expected


def save_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    headless = "--show" not in sys.argv
    print("מתחיל משיכת נתונים (API)...")
    rows, expected = scrape(headless=headless)

    if not rows:
        print("לא נמצאו נתונים.")
        sys.exit(1)

    save_csv(rows, OUTPUT)
    print(f'\nנשמר: {OUTPUT}')
    print(f'נמשכו: {len(rows)} מתוך {expected} הגרלות פתוחות')

    if len(rows) < expected:
        print(f"אזהרה: חסרות {expected - len(rows)} הגרלות!")

    print("\nTop 5 — סיכויים הכי טובים:")
    for i, r in enumerate(rows[:5], 1):
        print(
            f"  {i}. {r.get('יישוב')} | הגרלה {r.get('מספר הגרלה')} | "
            f"{r.get('דירות בהגרלה')} דירות / {r.get('נרשמים בהגרלה')} נרשמים | "
            f"יחס {r.get('יחס נרשמים/דירות')} | {r.get('אחוז סיכוי משוער')}"
        )


if __name__ == "__main__":
    main()
