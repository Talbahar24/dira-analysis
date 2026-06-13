#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ניתוח סיכויי זכייה — פרויקטי דירה בהנחה פתוחים להרשמה"""

import csv
import sys
from pathlib import Path


def parse_number(value):
    if value is None:
        return 0
    s = str(value).replace(",", "").replace("₪", "").replace("%", "").replace("*", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def analyze(projects):
    print("=" * 70)
    print("  ניתוח סיכויי זכייה — דירה בהנחה (פתוח להרשמה)")
    print("=" * 70)
    print(f'\nסה"כ הגרלות: {len(projects)}\n')

    ranked = []
    for p in projects:
        flats = parse_number(p.get("דירות בהגרלה", 0))
        registered = parse_number(p.get("נרשמים בהגרלה", 0))
        if flats <= 0 or registered <= 0:
            continue

        ratio = registered / flats
        chance_pct = (flats / registered) * 100
        ranked.append({
            "lottery": p.get("מספר הגרלה", "?"),
            "city": p.get("יישוב", "?"),
            "eligibility": p.get("זכאות", "?"),
            "deadline": p.get("סיום הרשמה", "?"),
            "flats": int(flats),
            "registered": int(registered),
            "ratio": ratio,
            "chance_pct": chance_pct,
            "price_sqm": p.get("מחיר למטר", "?"),
            "notes": p.get("הערות", ""),
            "contractor": p.get("קבלן", ""),
        })

    ranked.sort(key=lambda x: x["ratio"])

    print("הגרלות עם הסיכויים הטובים ביותר (יחס נמוך = יותר סיכוי)")
    print("-" * 70)
    print(f"{'#':>3}  {'יישוב':<14} {'הגרלה':>6}  {'דירות':>6}  {'נרשמים':>8}  {'יחס':>7}  {'סיכוי':>7}  {'מחיר/מ\"ר':>12}")
    print("-" * 70)

    for i, r in enumerate(ranked[:25], 1):
        print(
            f"{i:3}.  {r['city']:<14} {r['lottery']:>6}  "
            f"{r['flats']:6}  {r['registered']:8,}  {r['ratio']:7.1f}  "
            f"{r['chance_pct']:6.2f}%  {r['price_sqm']:>12}"
        )
        if r["notes"]:
            print(f"      הערות: {r['notes']}")

    print("\n" + "-" * 70)
    print("הגרלות עם הסיכויים הנמוכים ביותר (עמוסות)")
    print("-" * 70)
    for i, r in enumerate(reversed(ranked[-10:]), 1):
        print(
            f"{i:2}. {r['city']:<14} הגרלה {r['lottery']} | "
            f"{r['flats']} דירות / {r['registered']:,} נרשמים | יחס {r['ratio']:.1f}:1"
        )

    if ranked:
        avg_ratio = sum(r["ratio"] for r in ranked) / len(ranked)
        total_flats = sum(r["flats"] for r in ranked)
        total_registered = sum(r["registered"] for r in ranked)
        print("\n" + "=" * 70)
        print("  סיכום")
        print("=" * 70)
        print(f"  סה\"כ דירות:   {total_flats:,}")
        print(f"  סה\"כ נרשמים:  {total_registered:,}")
        print(f"  יחס ממוצע:     {avg_ratio:.1f} נרשמים לדירה")
        print(f"  סיכוי ממוצע:   {(total_flats/total_registered)*100:.2f}%")
        print(f"  יישובים:       {len({r['city'] for r in ranked})}")
        print("=" * 70)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dira_projects.csv")
    if not path.exists():
        print(f"קובץ לא נמצא: {path}")
        print("הרץ קודם את extract_dira_data.js בדפדפן")
        sys.exit(1)

    projects = load_csv(path)
    analyze(projects)


if __name__ == "__main__":
    main()
