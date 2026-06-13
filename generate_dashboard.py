#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""יוצר דשבורד מחקר מלא — בחירת 3 ערים לאסטרטגיית הרשמה"""

import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CSV_PATH = Path(__file__).parent / "dira_projects.csv"
HTML_PATH = Path(__file__).parent / "dashboard.html"
SITE_URL = "https://dira.moch.gov.il/ProjectsList"


def parse_number(value):
    if not value:
        return 0
    s = re.sub(r"[,₪*%\s]", "", str(value))
    try:
        return float(s)
    except ValueError:
        return 0


def load_projects(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    projects = []
    for row in rows:
        flats = parse_number(row.get("דירות בהגרלה"))
        registered = parse_number(row.get("נרשמים בהגרלה"))
        price = parse_number(row.get("מחיר למטר"))
        chance = (flats / registered * 100) if flats and registered else 0
        ratio = (registered / flats) if flats else 0
        notes = (row.get("הערות") or "").strip()
        projects.append({
            "lottery": row.get("מספר הגרלה", ""),
            "lotteryType": row.get("סוג הגרלה", ""),
            "city": row.get("יישוב", ""),
            "contractor": row.get("קבלן", "").strip(),
            "eligibility": row.get("זכאות", ""),
            "deadline": row.get("סיום הרשמה", "").replace("-", "/"),
            "flats": int(flats),
            "registered": int(registered),
            "price": int(price) if price else 0,
            "grant": row.get("מענק", ""),
            "chance": round(chance, 3),
            "ratio": round(ratio, 1),
            "notes": notes[:160] + ("..." if len(notes) > 160 else ""),
            "haredi": "חרדי" in notes or "חרדי" in notes,
        })
    return projects


def city_summary(projects):
    by_city = defaultdict(list)
    for p in projects:
        by_city[p["city"]].append(p)

    summary = []
    for city, items in by_city.items():
        flats = sum(i["flats"] for i in items)
        registered = sum(i["registered"] for i in items)
        chances = [i["chance"] / 100 for i in items if i["chance"] > 0]
        combined = (1 - eval_mult(chances)) * 100 if chances else 0
        prices = [i["price"] for i in items if i["price"] > 0]
        summary.append({
            "city": city,
            "projects": len(items),
            "flats": flats,
            "registered": registered,
            "avgChance": round((flats / registered * 100) if registered else 0, 2),
            "bestChance": round(max((i["chance"] for i in items), default=0), 2),
            "combinedChance": round(combined, 2),
            "minPrice": min(prices) if prices else 0,
            "maxPrice": max(prices) if prices else 0,
            "harediCount": sum(1 for i in items if i["haredi"]),
            "lotteries": [i["lottery"] for i in sorted(items, key=lambda x: -x["chance"])],
        })
    summary.sort(key=lambda x: x["combinedChance"], reverse=True)
    return summary


def eval_mult(chances):
    result = 1.0
    for c in chances:
        result *= (1 - c)
    return result


def build_html(projects, cities):
    total_flats = sum(p["flats"] for p in projects)
    total_registered = sum(p["registered"] for p in projects)
    avg_chance = (total_flats / total_registered * 100) if total_registered else 0
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")

    payload = json.dumps({
        "projects": projects,
        "cities": cities,
        "meta": {
            "generated": generated,
            "total": len(projects),
            "siteUrl": SITE_URL,
        },
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>דירה בהנחה — מרכז מחקר הגרלות</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419;
      --surface: #1a2332;
      --surface2: #243044;
      --border: #2d3a4f;
      --text: #e8edf4;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --accent2: #5eead4;
      --good: #34d399;
      --warn: #fbbf24;
      --bad: #f87171;
      --selected: #1e3a5f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .app {{ display: flex; min-height: 100vh; }}
    .sidebar {{
      width: 260px;
      background: var(--surface);
      border-left: 1px solid var(--border);
      padding: 20px 16px;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
    }}
    .sidebar h1 {{ font-size: 1.1rem; margin: 0 0 4px; }}
    .sidebar .meta {{ color: var(--muted); font-size: 0.78rem; margin-bottom: 20px; }}
    .nav-btn {{
      display: block;
      width: 100%;
      text-align: right;
      padding: 10px 12px;
      margin-bottom: 6px;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--text);
      cursor: pointer;
      font-size: 0.92rem;
    }}
    .nav-btn:hover {{ background: var(--surface2); }}
    .nav-btn.active {{
      background: var(--selected);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .main {{ flex: 1; padding: 24px 28px 48px; overflow-x: hidden; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 22px;
    }}
    .kpi {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
    }}
    .kpi .lbl {{ color: var(--muted); font-size: 0.78rem; }}
    .kpi .val {{ font-size: 1.5rem; font-weight: 700; margin-top: 2px; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    .card h2 {{ margin: 0 0 14px; font-size: 1rem; font-weight: 600; }}
    .card .hint {{ color: var(--muted); font-size: 0.8rem; margin-top: 8px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 1000px) {{ .grid2 {{ grid-template-columns: 1fr; }} .sidebar {{ display: none; }} }}
    .chart-h {{ height: 320px; position: relative; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    th, td {{ padding: 9px 11px; border-bottom: 1px solid var(--border); text-align: right; }}
    th {{ color: var(--muted); font-weight: 600; background: var(--surface2); position: sticky; top: 0; }}
    tr:hover td {{ background: rgba(61,139,253,0.06); }}
    .tbl-wrap {{ max-height: 480px; overflow: auto; border-radius: 8px; border: 1px solid var(--border); }}
    .good {{ color: var(--good); font-weight: 700; }}
    .mid {{ color: var(--warn); font-weight: 600; }}
    .bad {{ color: var(--bad); font-weight: 600; }}
    .controls {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; align-items: center; }}
    .controls input, .controls select {{
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 0.9rem;
    }}
    .city-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 12px;
    }}
    .city-card {{
      background: var(--surface2);
      border: 2px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      cursor: pointer;
      transition: border-color 0.15s;
    }}
    .city-card:hover {{ border-color: var(--accent); }}
    .city-card.selected {{
      border-color: var(--accent2);
      background: var(--selected);
    }}
    .city-card.disabled {{ opacity: 0.45; cursor: not-allowed; }}
    .city-card .name {{ font-weight: 700; font-size: 1rem; margin-bottom: 8px; }}
    .city-card .row {{ display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--muted); margin: 3px 0; }}
    .city-card .row span:last-child {{ color: var(--text); }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.72rem;
      background: var(--surface);
      border: 1px solid var(--border);
      margin-left: 4px;
    }}
    .badge.sel {{ background: #134e4a; border-color: var(--accent2); color: var(--accent2); }}
    .strategy-city {{
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 16px;
      overflow: hidden;
    }}
    .strategy-head {{
      background: var(--surface2);
      padding: 12px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .strategy-head h3 {{ margin: 0; font-size: 1rem; }}
    .strategy-stats {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.85rem; }}
    .strategy-stats div {{ color: var(--muted); }}
    .strategy-stats strong {{ color: var(--text); }}
    .callout {{
      background: #1a2f4a;
      border: 1px solid var(--accent);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 18px;
      font-size: 0.9rem;
    }}
    .callout strong {{ color: var(--accent2); }}
    .btn {{
      background: var(--accent);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.85rem;
    }}
    .btn:hover {{ filter: brightness(1.1); }}
    .btn.ghost {{
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .compare-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}
    @media (max-width: 900px) {{ .compare-grid {{ grid-template-columns: 1fr; }} }}
    .compare-col {{
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      min-height: 200px;
    }}
    .compare-col.empty {{ color: var(--muted); text-align: center; padding-top: 60px; }}
    .compare-col h4 {{ margin: 0 0 10px; color: var(--accent2); }}
    .metric-line {{ display: flex; justify-content: space-between; font-size: 0.84rem; margin: 6px 0; }}
    .pill-note {{ font-size: 0.75rem; color: var(--warn); }}
    .link-btn {{ color: var(--accent); text-decoration: none; font-size: 0.82rem; }}
    .link-btn:hover {{ text-decoration: underline; }}
    .slot-label {{ color: var(--muted); font-size: 0.8rem; margin-bottom: 10px; }}
    .selected-count {{ color: var(--accent2); font-weight: 700; }}
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <h1>דירה בהנחה</h1>
    <div class="meta">מרכז מחקר · {len(projects)} הגרלות · עודכן {generated}</div>
    <button class="nav-btn active" data-panel="overview">סקירה כללית</button>
    <button class="nav-btn" data-panel="cities">בחירת 3 ערים</button>
    <button class="nav-btn" data-panel="strategy">האסטרטגיה שלי</button>
    <button class="nav-btn" data-panel="compare">השוואת ערים</button>
    <button class="nav-btn" data-panel="table">כל ההגרלות</button>
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid var(--border)">
      <div class="slot-label">ערים שנבחרו: <span class="selected-count" id="sideCount">0/3</span></div>
      <div id="sideSelected" style="font-size:0.82rem;color:var(--muted)">טרם נבחרו ערים</div>
    </div>
  </aside>

  <main class="main">
    <section id="overview" class="panel active">
      <div class="kpis">
        <div class="kpi"><div class="lbl">הגרלות פתוחות</div><div class="val">{len(projects)}</div></div>
        <div class="kpi"><div class="lbl">יישובים</div><div class="val">{len(cities)}</div></div>
        <div class="kpi"><div class="lbl">סה"כ דירות</div><div class="val">{total_flats:,}</div></div>
        <div class="kpi"><div class="lbl">סה"כ נרשמים</div><div class="val">{total_registered:,}</div></div>
        <div class="kpi"><div class="lbl">סיכוי ממוצע</div><div class="val">{avg_chance:.2f}%</div></div>
      </div>
      <div class="callout">
        <strong>איך להשתמש:</strong> עבור ללשונית <em>בחירת 3 ערים</em>, בחר עד 3 יישובים.
        בכל עיר אפשר להירשם לכל הפרויקטים הפתוחים. בלשונית <em>האסטרטגיה שלי</em> תראה את כל ההגרלות לפי עיר,
        כולל הערכת סיכוי משולב אם נרשמים לכולן.
      </div>
      <div class="grid2">
        <div class="card">
          <h2>מפת תחרותיות — כל הגרלה</h2>
          <div class="chart-h"><canvas id="scatterChart"></canvas></div>
          <div class="hint">ציר X: נרשמים · ציר Y: סיכוי זכייה (%) · גודל בועה = מספר דירות</div>
        </div>
        <div class="card">
          <h2>סיכוי משולב לפי יישוב (הרשמה לכל הפרויקטים)</h2>
          <div class="chart-h"><canvas id="combinedChart"></canvas></div>
          <div class="hint">P(לפחות זכייה אחת) = 1 − ∏(1 − סיכוי_i) — הערכה סטטיסטית</div>
        </div>
      </div>
      <div class="card">
        <h2>דירות מול נרשמים — לפי יישוב</h2>
        <div class="chart-h"><canvas id="volumeChart"></canvas></div>
      </div>
    </section>

    <section id="cities" class="panel">
      <div class="callout">
        בחר <strong>עד 3 ערים</strong> — בכל עיר תוכל להירשם לכל הפרויקטים הפתוחים.
        לחץ על כרטיס עיר כדי לבחור/לבטל. הבחירה נשמרת אוטומטית.
      </div>
      <div class="controls">
        <input id="citySearch" placeholder="חפש יישוב..." />
        <select id="citySort">
          <option value="combined">מיון: סיכוי משולב (גבוה)</option>
          <option value="best">מיון: הגרלה הטובה ביותר</option>
          <option value="projects">מיון: מספר פרויקטים</option>
          <option value="flats">מיון: סה"כ דירות</option>
          <option value="name">מיון: שם (א-ת)</option>
        </select>
        <button class="btn ghost" id="clearCities">נקה בחירה</button>
      </div>
      <div class="city-grid" id="cityGrid"></div>
    </section>

    <section id="strategy" class="panel">
      <div class="callout" id="strategyCallout"></div>
      <div id="strategyContent"></div>
      <div class="card" id="strategySummary" style="display:none">
        <h2>סיכום אסטרטגיה — 3 הערים</h2>
        <div id="strategyTotals"></div>
        <div style="margin-top:14px">
          <a class="link-btn" href="{SITE_URL}" target="_blank">פתח אתר הרשמה רשמי ↗</a>
        </div>
      </div>
    </section>

    <section id="compare" class="panel">
      <div class="card">
        <h2>השוואה side-by-side</h2>
        <div class="compare-grid" id="compareGrid"></div>
      </div>
    </section>

    <section id="table" class="panel">
      <div class="controls">
        <input id="tblSearch" placeholder="חיפוש..." />
        <select id="tblCity"><option value="">כל היישובים</option></select>
        <select id="tblSort">
          <option value="chance-desc">סיכוי ↓</option>
          <option value="chance-asc">סיכוי ↑</option>
          <option value="registered-desc">נרשמים ↓</option>
          <option value="price-asc">מחיר למ"ר ↑</option>
        </select>
        <label style="color:var(--muted);font-size:0.85rem">
          <input type="checkbox" id="onlySelected" /> רק ערים שנבחרו
        </label>
      </div>
      <div class="card" style="padding:0">
        <div class="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>הגרלה</th><th>יישוב</th><th>קבלן</th><th>דירות</th>
                <th>נרשמים</th><th>יחס</th><th>סיכוי</th><th>מחיר/מ"ר</th><th>סיום</th><th>הערות</th>
              </tr>
            </thead>
            <tbody id="fullTable"></tbody>
          </table>
        </div>
      </div>
    </section>
  </main>
</div>

<script>
const DATA = {payload};
const PROJECTS = DATA.projects;
const CITIES = DATA.cities;
const MAX_CITIES = 3;
const LS_KEY = "dira_selected_cities";

let selectedCities = JSON.parse(localStorage.getItem(LS_KEY) || "[]").slice(0, MAX_CITIES);
let charts = {{}};

function chanceClass(v) {{
  if (v >= 2) return "good";
  if (v >= 0.5) return "mid";
  return "bad";
}}

function fmt(n) {{ return Number(n).toLocaleString("he-IL"); }}
function fmtPct(v) {{ return (Math.round(v * 100) / 100) + "%"; }}

function combinedChance(items) {{
  let p = 1;
  items.forEach(i => {{ if (i.chance > 0) p *= (1 - i.chance / 100); }});
  return (1 - p) * 100;
}}

function cityProjects(city) {{
  return PROJECTS.filter(p => p.city === city).sort((a,b) => b.chance - a.chance);
}}

function saveSelection() {{
  localStorage.setItem(LS_KEY, JSON.stringify(selectedCities));
  updateSide();
  renderStrategy();
  renderCompare();
  renderCityGrid();
  renderTable();
}}

function toggleCity(city) {{
  const idx = selectedCities.indexOf(city);
  if (idx >= 0) selectedCities.splice(idx, 1);
  else if (selectedCities.length < MAX_CITIES) selectedCities.push(city);
  saveSelection();
}}

function updateSide() {{
  document.getElementById("sideCount").textContent = selectedCities.length + "/" + MAX_CITIES;
  document.getElementById("sideSelected").innerHTML = selectedCities.length
    ? selectedCities.map(c => `<span class="badge sel">${{c}}</span>`).join(" ")
    : "טרם נבחרו ערים";
}}

function renderCityGrid() {{
  const q = document.getElementById("citySearch").value.trim();
  const sort = document.getElementById("citySort").value;
  let list = [...CITIES];
  if (q) list = list.filter(c => c.city.includes(q));
  const sorters = {{
    combined: (a,b) => b.combinedChance - a.combinedChance,
    best: (a,b) => b.bestChance - a.bestChance,
    projects: (a,b) => b.projects - a.projects,
    flats: (a,b) => b.flats - a.flats,
    name: (a,b) => a.city.localeCompare(b.city, "he"),
  }};
  list.sort(sorters[sort] || sorters.combined);

  document.getElementById("cityGrid").innerHTML = list.map(c => {{
    const sel = selectedCities.includes(c.city);
    const dis = !sel && selectedCities.length >= MAX_CITIES;
    return `<div class="city-card ${{sel?'selected':''}} ${{dis?'disabled':''}}" data-city="${{c.city}}">
      <div class="name">${{c.city}} ${{sel?'<span class="badge sel">נבחר</span>':''}}</div>
      <div class="row"><span>פרויקטים</span><span>${{c.projects}}</span></div>
      <div class="row"><span>דירות / נרשמים</span><span>${{fmt(c.flats)}} / ${{fmt(c.registered)}}</span></div>
      <div class="row"><span>סיכוי משולב</span><span class="${{chanceClass(c.combinedChance)}}">${{fmtPct(c.combinedChance)}}</span></div>
      <div class="row"><span>הגרלה הטובה</span><span class="${{chanceClass(c.bestChance)}}">${{fmtPct(c.bestChance)}}</span></div>
      <div class="row"><span>מחיר למ"ר</span><span>${{c.minPrice ? '₪'+fmt(c.minPrice)+'–₪'+fmt(c.maxPrice) : '—'}}</span></div>
      ${{c.harediCount ? `<div class="pill-note">${{c.harediCount}} פרויקטים עם צביון חרדי</div>` : ''}}
    </div>`;
  }}).join("");

  document.querySelectorAll(".city-card").forEach(el => {{
    el.addEventListener("click", () => {{
      if (el.classList.contains("disabled")) return;
      toggleCity(el.dataset.city);
    }});
  }});
}}

function renderStrategy() {{
  const callout = document.getElementById("strategyCallout");
  const content = document.getElementById("strategyContent");
  const summary = document.getElementById("strategySummary");
  const totals = document.getElementById("strategyTotals");

  if (!selectedCities.length) {{
    callout.innerHTML = "עבור ל<b>בחירת 3 ערים</b> ובחר יישובים. כאן תראה את כל ההגרלות שאליהן תוכל להירשם.";
    content.innerHTML = "";
    summary.style.display = "none";
    return;
  }}

  callout.innerHTML = `נבחרו <strong>${{selectedCities.length}}</strong> ערים. בכל עיר — הרשמה לכל ${{selectedCities.map(c => {{
    const n = CITIES.find(x => x.city===c)?.projects || 0;
    return n + " פרויקטים ב" + c;
  }}).join(", ")}}.`;

  let allItems = [];
  let totalProjects = 0;
  let totalFlats = 0;

  content.innerHTML = selectedCities.map(city => {{
    const items = cityProjects(city);
    const c = CITIES.find(x => x.city === city);
    const comb = combinedChance(items);
    allItems = allItems.concat(items);
    totalProjects += items.length;
    totalFlats += c?.flats || 0;

    const rows = items.map(p => `
      <tr>
        <td>${{p.lottery}}</td>
        <td>${{p.contractor}}</td>
        <td>${{fmt(p.flats)}}</td>
        <td>${{fmt(p.registered)}}</td>
        <td class="${{chanceClass(p.chance)}}">${{fmtPct(p.chance)}}</td>
        <td>${{p.price ? '₪'+fmt(p.price) : '—'}}</td>
        <td>${{p.deadline}}</td>
        <td>${{p.haredi ? '<span class="pill-note">חרדי</span>' : ''}}</td>
      </tr>`).join("");

    return `<div class="strategy-city">
      <div class="strategy-head">
        <h3>${{city}}</h3>
        <div class="strategy-stats">
          <div>פרויקטים: <strong>${{items.length}}</strong></div>
          <div>דירות: <strong>${{fmt(c?.flats||0)}}</strong></div>
          <div>סיכוי משולב: <strong class="${{chanceClass(comb)}}">${{fmtPct(comb)}}</strong></div>
        </div>
      </div>
      <div class="tbl-wrap" style="max-height:300px">
        <table>
          <thead><tr>
            <th>הגרלה</th><th>קבלן</th><th>דירות</th><th>נרשמים</th>
            <th>סיכוי</th><th>מחיר/מ"ר</th><th>סיום</th><th></th>
          </tr></thead>
          <tbody>${{rows}}</tbody>
        </table>
      </div>
    </div>`;
  }}).join("");

  const overallComb = combinedChance(allItems);
  summary.style.display = "block";
  totals.innerHTML = `
    <div class="strategy-stats" style="font-size:1rem">
      <div>סה"כ הרשמות נדרשות: <strong>${{totalProjects}}</strong> הגרלות</div>
      <div>סה"כ דירות בערים שנבחרו: <strong>${{fmt(totalFlats)}}</strong></div>
      <div>סיכוי משולב (כל ההגרלות ב-3 ערים): <strong class="${{chanceClass(overallComb)}}">${{fmtPct(overallComb)}}</strong></div>
    </div>
    <div class="hint" style="margin-top:10px">
      הסיכוי המשולב מניח הרשמה לכל פרויקט בנפרד. בפועל, ככל שתירשם להגרלות רבות יותר — הסיכוי לזכות באחת מהן עולה.
    </div>`;
}}

function renderCompare() {{
  const grid = document.getElementById("compareGrid");
  const slots = [0,1,2].map(i => selectedCities[i] || null);
  grid.innerHTML = slots.map((city, i) => {{
    if (!city) return `<div class="compare-col empty">עיר ${{i+1}}<br><small>לא נבחרה</small></div>`;
    const c = CITIES.find(x => x.city === city);
    const items = cityProjects(city);
    return `<div class="compare-col">
      <h4>${{city}}</h4>
      <div class="metric-line"><span>פרויקטים</span><strong>${{c.projects}}</strong></div>
      <div class="metric-line"><span>דירות</span><strong>${{fmt(c.flats)}}</strong></div>
      <div class="metric-line"><span>נרשמים</span><strong>${{fmt(c.registered)}}</strong></div>
      <div class="metric-line"><span>סיכוי משולב</span><strong class="${{chanceClass(c.combinedChance)}}">${{fmtPct(c.combinedChance)}}</strong></div>
      <div class="metric-line"><span>הגרלה הטובה</span><strong class="${{chanceClass(c.bestChance)}}">${{fmtPct(c.bestChance)}}</strong></div>
      <div class="metric-line"><span>מחיר למ"ר</span><strong>${{c.minPrice?'₪'+fmt(c.minPrice)+'–₪'+fmt(c.maxPrice):'—'}}</strong></div>
      <div style="margin-top:12px;font-size:0.8rem;color:var(--muted)">הגרלות: ${{c.lotteries.join(", ")}}</div>
    </div>`;
  }}).join("");
}}

function renderTable() {{
  const q = document.getElementById("tblSearch").value.trim().toLowerCase();
  const city = document.getElementById("tblCity").value;
  const sort = document.getElementById("tblSort").value;
  const onlySel = document.getElementById("onlySelected").checked;

  let rows = [...PROJECTS];
  if (onlySel && selectedCities.length) rows = rows.filter(p => selectedCities.includes(p.city));
  if (city) rows = rows.filter(p => p.city === city);
  if (q) rows = rows.filter(p => `${{p.lottery}} ${{p.city}} ${{p.contractor}} ${{p.notes}}`.toLowerCase().includes(q));

  const [key, dir] = sort.split("-");
  const mult = dir === "asc" ? 1 : -1;
  rows.sort((a,b) => ((a[key]||0) - (b[key]||0)) * mult);

  document.getElementById("fullTable").innerHTML = rows.map(p => `
    <tr>
      <td>${{p.lottery}}</td>
      <td>${{selectedCities.includes(p.city)?'<span class="badge sel">'+p.city+'</span>':p.city}}</td>
      <td>${{p.contractor}}</td>
      <td>${{fmt(p.flats)}}</td>
      <td>${{fmt(p.registered)}}</td>
      <td>${{p.ratio}}:1</td>
      <td class="${{chanceClass(p.chance)}}">${{fmtPct(p.chance)}}</td>
      <td>${{p.price?'₪'+fmt(p.price):'—'}}</td>
      <td>${{p.deadline}}</td>
      <td>${{p.haredi?'<span class="pill-note">חרדי</span>':''}} ${{p.notes?'<span class="badge">'+p.notes.slice(0,40)+'</span>':''}}</td>
    </tr>`).join("");
}}

function initCharts() {{
  Chart.defaults.color = "#8b9cb3";
  Chart.defaults.borderColor = "#2d3a4f";
  const opts = {{ responsive: true, maintainAspectRatio: false }};

  charts.scatter = new Chart(document.getElementById("scatterChart"), {{
    type: "bubble",
    data: {{
      datasets: [{{
        label: "הגרלות",
        data: PROJECTS.map(p => ({{
          x: p.registered, y: p.chance, r: Math.max(4, Math.min(18, p.flats / 15))
        }})),
        backgroundColor: PROJECTS.map(p => selectedCities.includes(p.city) ? "#5eead4aa" : "#3d8bfd66"),
      }}]
    }},
    options: {{ ...opts,
      scales: {{
        x: {{ title: {{ display: true, text: "נרשמים" }} }},
        y: {{ title: {{ display: true, text: "סיכוי זכייה (%)" }} }}
      }}
    }}
  }});

  const topC = CITIES.slice(0, 15);
  charts.combined = new Chart(document.getElementById("combinedChart"), {{
    type: "bar",
    data: {{
      labels: topC.map(c => c.city),
      datasets: [{{
        label: "סיכוי משולב (%)",
        data: topC.map(c => c.combinedChance),
        backgroundColor: topC.map(c => selectedCities.includes(c.city) ? "#5eead4" : "#3d8bfd"),
      }}]
    }},
    options: {{ ...opts, indexAxis: "y",
      scales: {{ x: {{ title: {{ display: true, text: "אחוז (%)" }} }} }}
    }}
  }});

  charts.volume = new Chart(document.getElementById("volumeChart"), {{
    type: "bar",
    data: {{
      labels: topC.map(c => c.city),
      datasets: [
        {{ label: "דירות", data: topC.map(c => c.flats), backgroundColor: "#3d8bfd" }},
        {{ label: "נרשמים", data: topC.map(c => c.registered), backgroundColor: "#f87171" }},
      ]
    }},
    options: {{ ...opts, scales: {{ y: {{ title: {{ display: true, text: "מספר" }} }} }} }}
  }});
}}

function refreshCharts() {{
  if (!charts.scatter) return;
  charts.scatter.data.datasets[0].backgroundColor = PROJECTS.map(p =>
    selectedCities.includes(p.city) ? "#5eead4aa" : "#3d8bfd66");
  charts.scatter.update();
  charts.combined.data.datasets[0].backgroundColor = CITIES.slice(0,15).map(c =>
    selectedCities.includes(c.city) ? "#5eead4" : "#3d8bfd");
  charts.combined.update();
}}

document.querySelectorAll(".nav-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.panel).classList.add("active");
  }});
}});

document.getElementById("citySearch").addEventListener("input", renderCityGrid);
document.getElementById("citySort").addEventListener("change", renderCityGrid);
document.getElementById("clearCities").addEventListener("click", () => {{ selectedCities = []; saveSelection(); refreshCharts(); }});
document.getElementById("tblSearch").addEventListener("input", renderTable);
document.getElementById("tblCity").addEventListener("change", renderTable);
document.getElementById("tblSort").addEventListener("change", renderTable);
document.getElementById("onlySelected").addEventListener("change", renderTable);

CITIES.map(c => c.city).sort((a,b)=>a.localeCompare(b,"he")).forEach(c => {{
  const o = document.createElement("option");
  o.value = c; o.textContent = c;
  document.getElementById("tblCity").appendChild(o);
}});

const origSave = saveSelection;
saveSelection = function() {{ origSave(); refreshCharts(); }};

initCharts();
renderCityGrid();
updateSide();
renderStrategy();
renderCompare();
renderTable();
</script>
</body>
</html>"""


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PATH
    if not path.exists():
        print(f"קובץ לא נמצא: {path}")
        sys.exit(1)

    projects = load_projects(path)
    cities = city_summary(projects)
    html = build_html(projects, cities)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"נוצר: {HTML_PATH}")
    print(f"{len(projects)} הגרלות, {len(cities)} יישובים")


if __name__ == "__main__":
    main()
