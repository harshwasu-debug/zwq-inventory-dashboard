"""Refresh Prices — pull the latest invoice observations into canonical_price_list
so recipe costs reflect current invoice reality.
"""
import datetime as dt
import json
import os
import shutil
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Dish_Costing.refresh_canonical_prices import (
    CANONICAL_FILE, OBSERVATIONS_FILE, REPORT_CSV,
    compute_refresh, write_report, apply_changes,
    SANITY_LOWER, SANITY_UPPER, WINDOW_RECENT_DAYS, WINDOW_FALLBACK_DAYS,
)

st.set_page_config(page_title="Refresh Prices", page_icon="💰", layout="wide")
st.markdown("## Refresh Canonical Prices from Invoice Observations")
st.caption("Pulls the latest dated prices from `price_observations.json` into the canonical price list used by recipe costing.")

# ---------------------------------------------------------------------------
# Run preview (always; cheap)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def _run_preview():
    canonical = json.load(open(CANONICAL_FILE, encoding="utf-8"))
    observations = json.load(open(OBSERVATIONS_FILE, encoding="utf-8"))
    today = dt.date.today()
    decisions = compute_refresh(observations, canonical.get("items", []), today)
    return canonical, decisions, today


canonical, decisions, today = _run_preview()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

by_action = {}
for d in decisions:
    by_action[d["action"]] = by_action.get(d["action"], 0) + 1

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total ingredients", len(decisions))
c2.metric("Will update", by_action.get("update", 0), help="Passed sanity check, ready to auto-apply")
c3.metric("Need review", by_action.get("review", 0), help="Suspicious change — manual approval needed")
c4.metric("No change", by_action.get("no_change", 0))
c5.metric("No data", by_action.get("skip", 0), help="No invoice observations in the last 365 days")

st.caption(
    f"Window: median of last 5 obs in {WINDOW_RECENT_DAYS}d (fallback: most-recent in {WINDOW_FALLBACK_DAYS}d). "
    f"Sanity bound: new price within {SANITY_LOWER}× to {SANITY_UPPER}× of current canonical, else flagged."
)

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

df = pd.DataFrame(decisions)

tabs = st.tabs([
    f"Will update ({by_action.get('update', 0)})",
    f"Review ({by_action.get('review', 0)})",
    f"No change ({by_action.get('no_change', 0)})",
    f"No data ({by_action.get('skip', 0)})",
])

display_cols = ["ingredient", "uom", "old_price", "new_price", "change_pct",
                "sanity", "basis", "n_used", "latest_date", "latest_supplier", "all_obs_count"]


def _show(filter_val):
    sub = df[df["action"] == filter_val][display_cols].copy()
    if "change_pct" in sub.columns:
        sub = sub.sort_values("change_pct", key=lambda s: s.abs(), ascending=False, na_position="last")
    st.dataframe(sub, use_container_width=True, hide_index=True)


with tabs[0]:
    st.caption("These will be auto-applied when you click Apply. Sanity-checked.")
    _show("update")

with tabs[1]:
    st.caption("Suspicious changes — usually a unit mismatch (case price vs unit price). Review and fix the source observation if needed.")
    _show("review")

with tabs[2]:
    _show("no_change")

with tabs[3]:
    st.caption("No trusted invoice observations in the last 365 days. Canonical price unchanged.")
    _show("skip")

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

st.divider()

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Download report (CSV)"):
        write_report(decisions, REPORT_CSV)
        with open(REPORT_CSV, "rb") as f:
            st.download_button("Save price_refresh_report.csv", f.read(),
                               file_name="price_refresh_report.csv", mime="text/csv")

with col2:
    n_update = by_action.get("update", 0)
    if n_update == 0:
        st.info("No safe updates to apply right now.")
    else:
        confirm = st.checkbox(f"Confirm: apply {n_update} sanity-checked price updates", key="confirm_apply")
        if confirm and st.button(f"Apply {n_update} updates", type="primary"):
            backup = CANONICAL_FILE.replace(".json", f"_backup_{today.strftime('%Y%m%d-%H%M%S')}-refresh.json")
            shutil.copy2(CANONICAL_FILE, backup)
            n = apply_changes(canonical, decisions, today)
            with open(CANONICAL_FILE, "w", encoding="utf-8") as f:
                json.dump(canonical, f, indent=2, ensure_ascii=False)
            st.cache_data.clear()
            st.success(f"Applied {n} price updates. Backup: `{os.path.basename(backup)}`. Recipe costs will reflect new prices on next load.")
            st.rerun()
