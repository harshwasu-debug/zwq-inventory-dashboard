"""ZwQ Calorie Tracker — personal app for Harsh & Evelina."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Calorie Tracker", page_icon="🥗", layout="wide")

st.title("🥗 Calorie Tracker")
st.caption("Personal tracker for Harsh & Evelina")

st.success("Scaffold deployed. Next: connect Google Sheet + load recipe data.")

with st.sidebar:
    st.header("Status")
    st.write("**Stage:** scaffold")
    st.write("**Next steps:**")
    st.markdown(
        "- Connect Google Sheet (meal log + targets)\n"
        "- Load recipes from `AI Strategy/Recipe_Data/`\n"
        "- Add calorie estimates per dish\n"
        "- Build meal logger\n"
        "- Build 'what can we eat' suggester"
    )
