# ZwQ Calorie Tracker

Personal calorie tracker for Harsh & Evelina, built on top of the ZwQ recipe library.

Separate from the main ZwQ business dashboard — own deploy, own URL, private access.

## Deploy (one-time setup)

### 1. Streamlit Cloud
- Go to https://share.streamlit.io → **New app**
- Repo: same as main app
- Branch: `main`
- **Main file path:** `calorie_tracker/streamlit_app.py`
- App URL: choose something like `zwq-calories`
- After deploy → **Settings → Sharing → set to "Only specific people"** and whitelist your + Evelina's email

### 2. Google Sheet for meal log
1. Create a new Google Sheet named `ZwQ Calorie Log` with two tabs:
   - `meals` — columns: `timestamp, date, eater, dish_brand, dish_name, portions, calories, notes`
   - `targets` — columns: `date, harsh_target, evelina_target`
2. Create a Google Cloud service account:
   - https://console.cloud.google.com → new project → enable **Google Sheets API** + **Google Drive API**
   - IAM → Service Accounts → Create → download JSON key
3. Share the Google Sheet with the service account's email (Editor)
4. In Streamlit Cloud → app **Settings → Secrets**, paste:
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "..."
   client_email = "..."
   client_id = "..."
   # ... (paste full JSON contents in TOML format)

   [sheet]
   id = "GOOGLE_SHEET_ID_FROM_URL"
   ```

## Local dev
```bash
cd calorie_tracker
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data sources
- Recipes: `../AI Strategy/Recipe_Data/*.json` (read-only)
- Meal log + targets: Google Sheet (read/write)
