"""Data helpers: recipe loading + Google Sheet I/O."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "AI Strategy" / "Recipe_Data"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MEALS_HEADER = ["timestamp", "date", "eater", "dish_brand", "dish_name", "portions", "calories", "notes"]
TARGETS_HEADER = ["date", "harsh_target", "evelina_target"]


# ---------- Recipes ----------

@st.cache_data(ttl=3600)
def load_recipes() -> pd.DataFrame:
    """Read all brand recipe JSONs into a flat DataFrame."""
    rows: list[dict[str, Any]] = []
    for path in sorted(RECIPE_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        brand = data.get("brand") or data.get("dataset") or path.stem
        for r in data.get("recipes", []):
            cal = r.get("calories_kcal")
            if cal is None:
                continue
            rows.append({
                "brand": r.get("brand") or brand,
                "name": r.get("recipe_name", "—"),
                "category": r.get("category", "—"),
                "calories": int(cal),
                "serves": r.get("serves") or 1,
                "label": f"{r.get('recipe_name', '?')} — {int(cal)} kcal",
            })
    df = pd.DataFrame(rows).sort_values(["brand", "name"]).reset_index(drop=True)
    return df


# ---------- Google Sheet ----------

@st.cache_resource
def _client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


@st.cache_resource
def _spreadsheet():
    return _client().open_by_key(st.secrets["sheet"]["id"])


def _ws(name: str):
    sh = _spreadsheet()
    try:
        return sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=1000, cols=10)
        header = MEALS_HEADER if name == "meals" else TARGETS_HEADER
        ws.append_row(header)
        return ws


def ensure_headers() -> None:
    """Write headers if the sheet is empty."""
    for name, header in (("meals", MEALS_HEADER), ("targets", TARGETS_HEADER)):
        ws = _ws(name)
        first = ws.row_values(1)
        if not first:
            ws.append_row(header)


def get_meals_df() -> pd.DataFrame:
    rows = _ws("meals").get_all_records()
    if not rows:
        return pd.DataFrame(columns=MEALS_HEADER)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["calories"] = pd.to_numeric(df["calories"], errors="coerce").fillna(0)
    df["portions"] = pd.to_numeric(df["portions"], errors="coerce").fillna(1)
    return df


def append_meal(eater: str, dish_brand: str, dish_name: str, portions: float, calories: float, notes: str = "") -> None:
    today = date.today()
    _ws("meals").append_row([
        datetime.now().isoformat(timespec="seconds"),
        today.isoformat(),
        eater,
        dish_brand,
        dish_name,
        float(portions),
        float(calories),
        notes,
    ])
    get_meals_df.clear() if hasattr(get_meals_df, "clear") else None


def get_targets_df() -> pd.DataFrame:
    rows = _ws("targets").get_all_records()
    if not rows:
        return pd.DataFrame(columns=TARGETS_HEADER)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for col in ("harsh_target", "evelina_target"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def latest_targets() -> tuple[int | None, int | None]:
    df = get_targets_df()
    if df.empty:
        return None, None
    last = df.iloc[-1]
    h = int(last["harsh_target"]) if pd.notna(last["harsh_target"]) else None
    e = int(last["evelina_target"]) if pd.notna(last["evelina_target"]) else None
    return h, e


def upsert_targets(target_date: date, harsh: int, evelina: int) -> None:
    """Insert or update the targets row for a given date."""
    ws = _ws("targets")
    rows = ws.get_all_records()
    for i, row in enumerate(rows, start=2):  # row 1 is header
        if str(row.get("date")) == target_date.isoformat():
            ws.update(f"A{i}:C{i}", [[target_date.isoformat(), int(harsh), int(evelina)]])
            return
    ws.append_row([target_date.isoformat(), int(harsh), int(evelina)])


# ---------- Calorie math ----------

def consumed_today(meals: pd.DataFrame, today: date) -> tuple[float, float]:
    """Return (harsh_kcal, evelina_kcal) consumed today.

    Eater values:
      - 'Harsh' → all to Harsh
      - 'Evelina' → all to Evelina
      - 'Together' → split 50/50
    """
    if meals.empty:
        return 0.0, 0.0
    today_meals = meals[meals["date"] == today]
    h = float(today_meals.loc[today_meals["eater"] == "Harsh", "calories"].sum())
    e = float(today_meals.loc[today_meals["eater"] == "Evelina", "calories"].sum())
    shared = float(today_meals.loc[today_meals["eater"] == "Together", "calories"].sum())
    return h + shared / 2, e + shared / 2
