"""ZwQ Calorie Tracker — personal app for Harsh & Evelina."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from helpers import (
    append_meal,
    consumed_today,
    ensure_headers,
    get_meals_df,
    latest_targets,
    load_recipes,
    upsert_targets,
)

st.set_page_config(page_title="Calorie Tracker", page_icon="🥗", layout="wide")
st.title("🥗 Calorie Tracker")
st.caption("Personal tracker for Harsh & Evelina")

# --- Boot: ensure sheet headers exist ---
try:
    ensure_headers()
except Exception as exc:
    st.error(f"Could not connect to Google Sheet: {exc}")
    st.stop()

recipes = load_recipes()
meals = get_meals_df()
today = date.today()

# --- Sidebar: daily targets ---
with st.sidebar:
    st.header("Daily targets")
    last_h, last_e = latest_targets()
    todays = meals  # placeholder; real targets come from targets sheet
    from helpers import get_targets_df  # local import to avoid cluttering top
    tdf = get_targets_df()
    todays_target = tdf[tdf["date"] == today] if not tdf.empty else pd.DataFrame()
    if not todays_target.empty:
        cur_h = int(todays_target.iloc[0]["harsh_target"])
        cur_e = int(todays_target.iloc[0]["evelina_target"])
    else:
        cur_h = last_h or 2000
        cur_e = last_e or 1600

    h_target = st.number_input("Harsh", min_value=500, max_value=5000, value=cur_h, step=50)
    e_target = st.number_input("Evelina", min_value=500, max_value=5000, value=cur_e, step=50)
    if st.button("Save targets for today", use_container_width=True):
        upsert_targets(today, h_target, e_target)
        st.success("Saved.")
        st.rerun()

    st.divider()
    st.caption(f"Recipes loaded: **{len(recipes)}** across **{recipes['brand'].nunique()}** brands")

# --- Top: today's progress ---
h_done, e_done = consumed_today(meals, today)
h_left = max(h_target - h_done, 0)
e_left = max(e_target - e_done, 0)

c1, c2 = st.columns(2)
with c1:
    st.metric("Harsh — consumed", f"{int(h_done)} kcal", f"{int(h_left)} left")
    st.progress(min(h_done / h_target, 1.0) if h_target else 0)
with c2:
    st.metric("Evelina — consumed", f"{int(e_done)} kcal", f"{int(e_left)} left")
    st.progress(min(e_done / e_target, 1.0) if e_target else 0)

st.divider()

# --- Tabs ---
tab_log, tab_suggest, tab_today = st.tabs(["➕ Log meal", "🔍 What can we eat?", "📋 Today's log"])

# ---- LOG MEAL ----
with tab_log:
    st.subheader("Log a meal")
    eater = st.radio("Who's eating?", ["Harsh", "Evelina", "Together"], horizontal=True)
    brands = sorted(recipes["brand"].unique())
    brand = st.selectbox("Brand", brands)
    brand_recipes = recipes[recipes["brand"] == brand].sort_values("name")
    dish_label = st.selectbox("Dish", brand_recipes["label"].tolist())
    dish_row = brand_recipes[brand_recipes["label"] == dish_label].iloc[0]
    portions = st.number_input("Portions", min_value=0.25, max_value=10.0, value=1.0, step=0.25)
    calories = float(dish_row["calories"]) * portions
    notes = st.text_input("Notes (optional)", "")
    st.info(f"**{calories:.0f} kcal** total" + (" — split 50/50" if eater == "Together" else ""))
    if st.button("Log meal", type="primary"):
        append_meal(eater, brand, dish_row["name"], portions, calories, notes)
        st.success(f"Logged {dish_row['name']} ({calories:.0f} kcal) for {eater}.")
        st.rerun()

# ---- SUGGEST ----
with tab_suggest:
    st.subheader("Dishes that fit your remaining budget")
    mode = st.radio("Eating", ["Together", "Harsh only", "Evelina only"], horizontal=True)
    if mode == "Harsh only":
        budget = h_left
        st.caption(f"Harsh has **{int(h_left)} kcal** left")
    elif mode == "Evelina only":
        budget = e_left
        st.caption(f"Evelina has **{int(e_left)} kcal** left")
    else:
        # Together: each gets half the dish, so dish cap = 2x the smaller remaining
        budget = 2 * min(h_left, e_left)
        st.caption(f"Together — Harsh has {int(h_left)} left, Evelina {int(e_left)} left. Dish cap: **{int(budget)} kcal**")

    portions_pick = st.slider("Portions per person (or per shared dish)", 0.5, 2.0, 1.0, 0.25)
    fits = recipes.copy()
    fits["effective_kcal"] = fits["calories"] * portions_pick
    fits = fits[fits["effective_kcal"] <= budget].sort_values("effective_kcal", ascending=False)
    if fits.empty:
        st.warning("No dishes fit. Lower the portion size or it's water o'clock 💧")
    else:
        st.dataframe(
            fits[["brand", "name", "category", "calories", "effective_kcal"]]
                .rename(columns={"calories": "kcal/serving", "effective_kcal": "kcal at chosen portions"})
                .head(50),
            hide_index=True,
            use_container_width=True,
        )

# ---- TODAY'S LOG ----
with tab_today:
    st.subheader(f"Logged meals — {today.isoformat()}")
    today_rows = meals[meals["date"] == today] if not meals.empty else meals
    if today_rows.empty:
        st.info("Nothing logged yet today.")
    else:
        st.dataframe(
            today_rows[["timestamp", "eater", "dish_brand", "dish_name", "portions", "calories", "notes"]],
            hide_index=True,
            use_container_width=True,
        )
