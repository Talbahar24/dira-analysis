#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""המלצות סטטיסטיות — איזה יישובים ופרויקטים כדאי להירשם"""

import csv
import json
import math
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

CSV = Path(__file__).parent / "dira_projects.csv"
OUT = Path(__file__).parent / "recommendations.json"


def parse_num(v):
    if not v:
        return 0
    try:
        return float(re.sub(r"[,₪*%\s]", "", str(v)))
    except ValueError:
        return 0


def load():
    with open(CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def project_stats(row):
    flats = int(parse_num(row.get("דירות בהגרלה")))
    reg = int(parse_num(row.get("נרשמים בהגרלה")))
    price = int(parse_num(row.get("מחיר למטר")))
    p = flats / reg if reg else 0
    # score: balance chance with meaningful pool (log flats weight)
    score = p * math.log1p(flats) * 100
    return {
        "lottery": row["מספר הגרלה"],
        "city": row["יישוב"],
        "contractor": row.get("קבלן", "").strip(),
        "flats": flats,
        "registered": reg,
        "price": price,
        "p": p,
        "p_pct": round(p * 100, 3),
        "score": round(score, 4),
        "deadline": row.get("סיום הרשמה", ""),
        "haredi": "חרדי" in (row.get("הערות") or ""),
        "notes": (row.get("הערות") or "")[:80],
    }


def combined_p(probs):
    """P(לפחות הצלחה אחת) — אירועים בלתי תלויים."""
    prod = 1.0
    for p in probs:
        prod *= 1 - p
    return 1 - prod


def wilson_lower_bound(successes, trials, z=1.96):
    """רף תחתון לרווח סמך 95% ליחס הצלחה (שמרני)."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    denom = 1 + z**2 / trials
    center = p + z**2 / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    return max(0, (center - margin) / denom)


def analyze():
    rows = load()
    projects = [project_stats(r) for r in rows]
    projects.sort(key=lambda x: -x["score"])

    by_city = defaultdict(list)
    for p in projects:
        by_city[p["city"]].append(p)

    city_stats = []
    for city, items in by_city.items():
        probs = [i["p"] for i in items if i["p"] > 0]
        flats = sum(i["flats"] for i in items)
        reg = sum(i["registered"] for i in items)
        comb = combined_p(probs)
        # conservative bound per city (aggregate)
        wilson = wilson_lower_bound(flats, reg)
        city_stats.append({
            "city": city,
            "n_projects": len(items),
            "flats": flats,
            "registered": reg,
            "combined_p_pct": round(comb * 100, 2),
            "wilson_lb_pct": round(wilson * 100, 3),
            "best_single_pct": round(max(i["p_pct"] for i in items), 2),
            "avg_price": round(sum(i["price"] for i in items if i["price"]) / max(1, sum(1 for i in items if i["price"]))),
            "haredi": sum(1 for i in items if i["haredi"]),
            "lotteries": [i["lottery"] for i in sorted(items, key=lambda x: -x["p"])],
        })

    city_stats.sort(key=lambda x: -x["combined_p_pct"])

    # אופטימיזציה: 3 ערים שממקסמות סיכוי משולב
    best_triple = None
    best_triple_p = 0
    for combo in combinations(city_stats, 3):
        all_probs = []
        for c in combo:
            for item in by_city[c["city"]]:
                if item["p"] > 0:
                    all_probs.append(item["p"])
        cp = combined_p(all_probs)
        if cp > best_triple_p:
            best_triple_p = cp
            best_triple = combo

    # top 10 projects by statistical score
    top_projects = projects[:15]

    # top projects excluding ultra-competitive (p < 0.3%)
    balanced = [p for p in projects if p["p_pct"] >= 0.3]
    balanced.sort(key=lambda x: -x["score"])

    # triple alternatives: greedy by city combined_p
    greedy3 = city_stats[:3]

    result = {
        "methodology": {
            "model": "הנחת אירועים בלתי תלויים בין הגרלות",
            "combined": "P(≥1 זכייה) = 1 − ∏(1 − p_i), p_i = דירות/נרשמים",
            "score": "p × ln(1+דירות) — מאזן סיכוי עם גודל מלאי דירות",
            "wilson": "רף תחתון 95% ליחס דירות/נרשמים (שמרני)",
            "constraint": "עד 3 יישובים, הרשמה לכל הפרויקטים בכל יישוב",
        },
        "summary": {
            "total_lotteries": len(projects),
            "total_cities": len(city_stats),
        },
        "top_projects": top_projects,
        "top_balanced_projects": balanced[:10],
        "top_cities": city_stats[:10],
        "greedy_3_cities": greedy3,
        "optimal_3_cities": [
            {
                **c,
                "projects_detail": [
                    {k: v for k, v in p.items() if k != "notes"}
                    for p in sorted(by_city[c["city"]], key=lambda x: -x["p"])
                ],
            }
            for c in best_triple
        ],
        "optimal_3_combined_pct": round(best_triple_p * 100, 2),
        "optimal_3_total_registrations": sum(c["n_projects"] for c in best_triple),
    }
    return result


def main():
    r = analyze()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

    print("=" * 72)
    print("  המלצות סטטיסטיות — דירה בהנחה")
    print("=" * 72)

    print("\n>> TOP 10 פרויקטים בודדים (ציון: סיכוי x log(דירות))")
    print("-" * 72)
    for i, p in enumerate(r["top_projects"][:10], 1):
        print(
            f"{i:2}. הגרלה {p['lottery']:>5} | {p['city']:<14} | "
            f"{p['flats']:3} דירות / {p['registered']:>6,} נרשמים | "
            f"סיכוי {p['p_pct']:.2f}% | מחיר ₪{p['price']:,}" if p["price"] else
            f"{i:2}. הגרלה {p['lottery']:>5} | {p['city']:<14} | "
            f"{p['flats']:3} דירות / {p['registered']:>6,} נרשמים | סיכוי {p['p_pct']:.2f}%"
        )

    print("\n>> TOP 5 יישובים — סיכוי משולב (הרשמה לכל הפרויקטים בעיר)")
    print("-" * 72)
    for i, c in enumerate(r["top_cities"][:5], 1):
        print(
            f"{i}. {c['city']:<14} | {c['n_projects']} פרויקטים | "
            f"{c['flats']} דירות | סיכוי משולב {c['combined_p_pct']:.2f}% | "
            f"רף שמרני {c['wilson_lb_pct']:.2f}%"
        )

    print("\n>> שילוב אופטימלי של 3 יישובים (מקסום סיכוי משולב)")
    print("-" * 72)
    names = [c["city"] for c in r["optimal_3_cities"]]
    print(f"ערים: {' + '.join(names)}")
    print(f"סה\"כ הרשמות: {r['optimal_3_total_registrations']} הגרלות")
    print(f"סיכוי משולב לזכות לפחות בדירה אחת: {r['optimal_3_combined_pct']:.2f}%")
    for c in r["optimal_3_cities"]:
        print(f"\n  * {c['city']} ({c['n_projects']} פרויקטים, סיכוי משולב {c['combined_p_pct']:.2f}%):")
        for p in c["projects_detail"]:
            print(f"     - הגרלה {p['lottery']} — {p['flats']} דירות, {p['registered']:,} נרשמים, סיכוי {p['p_pct']:.2f}%")

    print(f"\nנשמר: {OUT}")


if __name__ == "__main__":
    main()
