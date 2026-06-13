# דירה בהנחה — מרכז מחקר הגרלות

דשבורד לניתוח 82 ההגרלות הפתוחות באתר [dira.moch.gov.il](https://dira.moch.gov.il/ProjectsList).

## פריסה חינמית (GitHub Pages)

1. צור repo חדש ב-GitHub (Public)
2. העלה את הקבצים:
   ```bash
   cd dira-analysis
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USER/dira-analysis.git
   git push -u origin main
   ```
3. ב-GitHub: **Settings → Pages**
   - **Source:** Deploy from a branch
   - **Branch:** `gh-pages` → `/ (root)` → Save
4. לך ל-**Actions** → **Update data and deploy** → **Run workflow**
5. האתר יעלה לכתובת: `https://Talbahar24.github.io/dira-analysis/`

הנתונים מתעדכנים אוטומטית כל יום ב-09:00 (שעון ישראל).

## הרצה מקומית

```bash
pip install -r requirements.txt
playwright install chromium
python scrape_dira.py
python generate_dashboard.py
# פתח dashboard.html
```
