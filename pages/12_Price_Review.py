"""
Canonical Price Review — Human-approved refresh of canonical_price_list.json.

For each canonical ingredient, shows the most recent 3 invoice observations with
full pack context (supplier, date, unit, pack description, raw price). You
Accept / Reject / Edit each proposed price change. Decisions persist so re-visiting
only shows new observations.

Why this exists: auto-refresh corrupted prices twice (case-vs-piece and pack-alias
issues). Supplier pack notations vary too wildly for safe automation without
per-item judgement.
"""
import streamlit as st
import pandas as pd
import json, os, re, sys, shutil
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher


def parse_pack_from_name(name: str):
    """Parse pack size from invoice item name.

    Returns (pack_size: int, explanation: str) or (None, "").

    Examples:
      "Clear Sauce Cup 2OZ - 1 X 2000 PCS"  -> (2000, "2000 pcs/pack")
      "Thick & Chunky Salsa 6x2.17 kg"       -> (6,    "6 pcs/case, 2.17 kg each")
      "Ajinomoto 24/500gm"                   -> (24,   "24 pcs/case, 500gm each")
      "Coke 300ml 1x24 Can"                  -> (24,   "24 cans/case")
      "Plain Bread Bun 6 Pcs Pac"            -> (6,    "6 pcs/pack")
    """
    if not name:
        return None, ""
    s = name.lower()

    # "1 X 2000 PCS" / "1x500 pcs" / "1 X 2000 P" -> pack = second number
    m = re.search(r"\b(\d+)\s*[x×]\s*(\d+)\s*(?:pcs?|pkt|pack|p\b|nos|units?)", s)
    if m:
        return int(m.group(2)), f"{m.group(2)} pcs/pack"

    # "1x24 can" / "20x6 pc" -> pack = second number (items per pack)
    m = re.search(r"\b(\d+)\s*[x×]\s*(\d+)\s*(?:can|bottle|ea|dozen|dz)\b", s)
    if m:
        return int(m.group(2)), f"{m.group(2)} items/pack"

    # "6x2.5kg" / "6 x 2.17 kg" -> pack = first number (count of units)
    m = re.search(r"\b(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(kg|kgs|ltr|l\b|g\b|gm|gms|ml)", s)
    if m:
        n1, n2, u = m.group(1), m.group(2), m.group(3)
        return int(n1), f"{n1} pcs/case, {n2}{u} each"

    # "24/500gm" / "12/510 GMS" / "6/A10" -> pack = first number
    m = re.search(r"\b(\d+)\s*/\s*(?:[aA]?\d+(?:\.\d+)?)\s*(?:gm|gms|g\b|ml|kg|oz|pcs?|pkt)", s)
    if m:
        return int(m.group(1)), f"{m.group(1)} pcs/case"

    # "6 Pcs Pac" / "10 Pcs Pkt" -> pack = first number
    m = re.search(r"\b(\d+)\s*pcs?\s+(?:pac|pack|pkt)\b", s)
    if m:
        return int(m.group(1)), f"{m.group(1)} pcs/pack"

    # "20X8 Pc Ambient" / "20 x 6 Pc" -> second number
    m = re.search(r"\b(\d+)\s*[x×]\s*(\d+)\s*pc\b", s)
    if m:
        return int(m.group(2)), f"{m.group(2)} pcs/pack"

    # "6/A10" -> 6 cans of A10 size (MH Enterprises convention)
    m = re.search(r"\b(\d+)\s*/\s*[aA]\d+\b", s)
    if m:
        return int(m.group(1)), f"{m.group(1)} cans/case"

    return None, ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_json, save_json, CANONICAL_PRICE_FILE, INVOICES_DIR

# ---------------------------------------------------------------------------

CONSOLIDATED_INVOICES = r"E:/Cloud Kitchen/Invoices/_archive/all_invoices_consolidated.json"
DECISIONS_FILE = os.path.join(INVOICES_DIR, "price_review_decisions.json")

UOM_ALIASES = {
    "kg": {"kg", "kgs", "kilogram", "kilograms"},
    "piece": {"piece", "pc", "pcs", "pieces", "nos", "each", "ea"},
    "l": {"l", "ltr", "litre", "liter"},
    "ml": {"ml"},
    "g": {"g", "gm", "gms", "gram"},
    "ctn": {"ctn", "carton", "cartons", "case", "cases"},
    "pac": {"pac", "pack", "pkt", "packet", "packets"},
    "bag": {"bag", "bags"},
    "box": {"box", "boxes"},
}


def norm_unit(u: str) -> str:
    s = (u or "").lower().strip()
    for canon, aliases in UOM_ALIASES.items():
        if s in aliases:
            return canon
    return s


def similarity(a, b):
    return SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()


st.set_page_config(page_title="Price Review", page_icon="✅", layout="wide")
st.markdown("## Canonical Price Review")
st.caption("Human-approved refresh of canonical ingredient prices from invoice observations")

# ==================== EXCEL BULK REVIEW ====================
with st.expander("📊 Excel bulk review (recommended for 288+ items)", expanded=True):
    st.markdown(
        """Download a single Excel file with two tabs:

        - **Tab 1: Existing Ingredients** — review 288 canonical items with observation data. Fill decisions (Accept/Reject/Custom) in the yellow column.
        - **Tab 2: Unmatched Items** — 741 invoice items not in your canonical list. Decide Add / Map / Ignore.

        Review in Excel on desktop, then re-upload here to apply all decisions at once."""
    )
    xc1, xc2 = st.columns(2)

    with xc1:
        if st.button("🔄 Regenerate canonical_review.xlsx", use_container_width=True,
                     help="Rebuild the Excel file from latest observations + canonical list"):
            import subprocess
            result = subprocess.run(
                ["python", os.path.join(os.path.dirname(os.path.dirname(__file__)), "Invoices", "generate_canonical_review_xlsx.py")],
                capture_output=True, text=True,
            )
            if result.returncode == 0 or "Written:" in result.stdout:
                st.success("Regenerated!")
            else:
                st.error(f"Error: {result.stderr[:500]}")

        xlsx_path = os.path.join(INVOICES_DIR, "canonical_review.xlsx")
        if os.path.exists(xlsx_path):
            with open(xlsx_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download canonical_review.xlsx",
                    data=f.read(),
                    file_name="canonical_review.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    with xc2:
        uploaded = st.file_uploader("⬆️ Upload completed Excel", type=["xlsx"],
                                     help="Upload the filled-in canonical_review.xlsx to preview and apply decisions.")
        if uploaded:
            # Save temp copy for apply script
            tmp_path = os.path.join(INVOICES_DIR, "canonical_review_uploaded.xlsx")
            with open(tmp_path, "wb") as f:
                f.write(uploaded.read())

            prev_col, apply_col = st.columns(2)
            with prev_col:
                if st.button("🔍 Preview changes (dry-run)", use_container_width=True):
                    import subprocess
                    result = subprocess.run(
                        ["python",
                         os.path.join(os.path.dirname(os.path.dirname(__file__)), "Invoices", "apply_canonical_review_xlsx.py"),
                         "--preview", "--file", tmp_path],
                        capture_output=True, text=True,
                    )
                    st.code(result.stdout or result.stderr, language="text")
            with apply_col:
                if st.button("✅ Apply decisions for real", type="primary", use_container_width=True):
                    import subprocess
                    result = subprocess.run(
                        ["python",
                         os.path.join(os.path.dirname(os.path.dirname(__file__)), "Invoices", "apply_canonical_review_xlsx.py"),
                         "--file", tmp_path],
                        capture_output=True, text=True,
                    )
                    st.code(result.stdout or result.stderr, language="text")
                    st.cache_data.clear()

st.markdown("---")
st.markdown("### Or: review one-by-one in the UI below (for spot-edits)")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

@st.cache_data
def load_all():
    canonical = load_json(CANONICAL_PRICE_FILE)
    if os.path.exists(CONSOLIDATED_INVOICES):
        with open(CONSOLIDATED_INVOICES, encoding="utf-8") as f:
            invoices_data = json.load(f)
            invoices = invoices_data.get("invoices", invoices_data) if isinstance(invoices_data, dict) else invoices_data
    else:
        invoices = []
    decisions = load_json(DECISIONS_FILE, default={})
    return canonical, invoices, decisions


def save_decisions(decisions):
    save_json(DECISIONS_FILE, decisions)


def build_worklist(canonical, invoices, decisions, threshold_pct=5.0):
    """Return a list of review items, sorted by |change_pct| desc."""
    # Collect observations by item name and unit
    obs_by_name = defaultdict(list)
    for inv in invoices:
        if inv.get("_dup_of"):
            continue
        date = inv.get("invoice_date", "")
        supplier = inv.get("_supplier_canonical", inv.get("supplier_name", ""))
        for item in inv.get("items", []) or []:
            name = (item.get("item_name") or "").strip()
            if not name:
                continue
            up = item.get("unit_price") or 0
            if up <= 0:
                qty = item.get("quantity") or 0
                tp = item.get("total_price") or 0
                if qty > 0 and tp > 0:
                    up = tp / qty
            if up <= 0:
                continue
            obs_by_name[name.lower()].append({
                "date": date,
                "supplier": supplier,
                "unit_price": up,
                "unit_raw": item.get("unit", ""),
                "unit_norm": norm_unit(item.get("unit", "")),
                "item_name": name,
                "quantity": item.get("quantity"),
                "total_price": item.get("total_price"),
                "pack_size": item.get("pack_size"),
                "pack_uom": item.get("pack_uom"),
                "case_price": item.get("case_price"),
            })

    # Pre-sort obs by date desc
    for lst in obs_by_name.values():
        lst.sort(key=lambda o: o.get("date") or "", reverse=True)

    worklist = []
    for item in canonical.get("items", []):
        ing = item["ingredient"]
        sup_item = item.get("supplier_item", "")
        canon_uom = norm_unit(item.get("uom", ""))
        current = item.get("price_per_unit", 0) or 0

        # Collect candidates: exact name, supplier_item, fuzzy
        candidates = []
        for nkey in [ing.lower(), sup_item.lower()]:
            if nkey and nkey in obs_by_name:
                candidates.extend(obs_by_name[nkey])
        if not candidates:
            best_name, best_sim = None, 0
            for obs_name in obs_by_name:
                s = similarity(ing, obs_name)
                if s > best_sim:
                    best_sim, best_name = s, obs_name
            if best_sim >= 0.80:
                candidates.extend(obs_by_name[best_name])

        if not candidates:
            continue

        # Take top 3 most recent
        recent = candidates[:3]
        # Propose: latest observation where unit matches canonical uom, else latest
        matching_unit = [c for c in recent if c["unit_norm"] == canon_uom]
        proposed = matching_unit[0] if matching_unit else recent[0]
        new_price = round(proposed["unit_price"], 4)
        change_pct = round((new_price - current) / current * 100, 1) if current else 0

        # Apply prior decision if exists
        key = ing
        prior = decisions.get(key, {})

        worklist.append({
            "ingredient": ing,
            "canonical_uom": item.get("uom"),
            "current_price": current,
            "proposed_price": new_price,
            "change_pct": change_pct,
            "unit_match": bool(matching_unit),
            "observations": recent,
            "canonical_item": item,
            "prior_action": prior.get("action"),
            "prior_price": prior.get("accepted_price"),
        })

    # Sort by abs(change_pct) desc, but put unresolved first
    worklist.sort(key=lambda w: (w["prior_action"] is not None, -abs(w["change_pct"])))
    return worklist


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

canonical, invoices, decisions = load_all()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Canonical items", len(canonical.get("items", [])))
col2.metric("Invoices loaded", len(invoices))
col3.metric("Decisions saved", len(decisions))
col4.metric("Last canonical gen", canonical.get("generated_date", "–"))

st.markdown("---")

# Controls
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    threshold = st.slider("Min % change to review", 0.0, 100.0, 5.0, 0.5,
        help="Skip ingredients whose proposed price is within this % of current.")
with c2:
    hide_resolved = st.checkbox("Hide already-decided", value=True)
with c3:
    show_only_unit_match = st.checkbox("Only unit-matched proposals", value=False,
        help="Hide items where the latest observation's unit doesn't match the canonical UOM.")

worklist = build_worklist(canonical, invoices, decisions)
filtered = [
    w for w in worklist
    if abs(w["change_pct"]) >= threshold
    and (not hide_resolved or w["prior_action"] is None)
    and (not show_only_unit_match or w["unit_match"])
]

st.info(f"**{len(filtered)}** items to review (of {len(worklist)} with observations).")

if not filtered:
    st.success("Nothing to review with these filters. Lower the threshold or uncheck 'Hide already-decided'.")
    st.stop()

# ========================================================================
# BULK AUTO-APPLY — the highest-leverage button
# ========================================================================
st.markdown("### ⚡ Bulk auto-apply (safe items only)")
st.caption("Auto-approve updates that meet strict safety rules. You only manually review the tricky ones.")

auto_cols = st.columns(4)
with auto_cols[0]:
    auto_max_change = st.number_input("Max |change %|", 0.0, 200.0, 50.0, 5.0,
        help="Ignore proposals beyond this magnitude — too risky to auto-approve.")
with auto_cols[1]:
    require_unit_match = st.checkbox("Require unit match", value=True,
        help="Only auto-apply when observation unit matches canonical UOM.")
with auto_cols[2]:
    allow_pack_parse = st.checkbox("Accept parsed packs", value=True,
        help="If unit doesn't match but pack_size was parsed from item name, use pack-conversion.")
with auto_cols[3]:
    min_obs_price = st.number_input("Min obs price (AED)", 0.0, 10.0, 0.05, 0.05,
        help="Reject proposals below this — likely OCR zero/artifact.")

if st.button("🚀 Auto-apply all safe updates", type="primary", use_container_width=True):
    applied_count = 0
    pack_converted = 0
    skipped_unsafe = 0
    for w in worklist:
        if w["prior_action"] is not None:
            continue
        if abs(w["change_pct"]) > auto_max_change:
            skipped_unsafe += 1
            continue
        if w["proposed_price"] < min_obs_price:
            skipped_unsafe += 1
            continue

        # Case 1: unit matches directly
        if w["unit_match"]:
            decisions[w["ingredient"]] = {
                "action": "auto_accept_unit_match",
                "accepted_price": w["proposed_price"],
                "old_price": w["current_price"],
                "change_pct": w["change_pct"],
                "timestamp": datetime.now().isoformat(),
            }
            applied_count += 1
            continue

        if not require_unit_match:
            # Accept even without unit match if allowed
            decisions[w["ingredient"]] = {
                "action": "auto_accept_no_unit_match",
                "accepted_price": w["proposed_price"],
                "old_price": w["current_price"],
                "change_pct": w["change_pct"],
                "timestamp": datetime.now().isoformat(),
            }
            applied_count += 1
            continue

        # Case 2: pack parsed from at least one observation
        if allow_pack_parse:
            detected = [
                parse_pack_from_name(o.get("item_name", ""))[0]
                for o in w["observations"]
            ]
            detected = [d for d in detected if d and d > 1]
            if detected:
                # Use most-common detected pack
                from collections import Counter
                pack = Counter(detected).most_common(1)[0][0]
                # Case/pack price is the most-recent observation's unit_price
                case_price = w["observations"][0].get("unit_price", 0)
                per_unit = round(case_price / pack, 4)
                # Sanity: reject if per_unit implausibly small (unit parse was wrong)
                if per_unit < min_obs_price:
                    skipped_unsafe += 1
                    continue
                # Change pct check on final per-unit price
                final_change = (per_unit - w["current_price"]) / w["current_price"] * 100 if w["current_price"] else 0
                if abs(final_change) > auto_max_change:
                    skipped_unsafe += 1
                    continue
                decisions[w["ingredient"]] = {
                    "action": "auto_accept_pack_converted",
                    "accepted_price": per_unit,
                    "case_price_used": case_price,
                    "pack_size_used": pack,
                    "old_price": w["current_price"],
                    "change_pct": round(final_change, 1),
                    "timestamp": datetime.now().isoformat(),
                }
                applied_count += 1
                pack_converted += 1
                continue

        skipped_unsafe += 1

    save_decisions(decisions)
    st.cache_data.clear()
    st.success(
        f"✅ Auto-applied **{applied_count}** decisions ({pack_converted} via pack conversion). "
        f"Skipped {skipped_unsafe} as needing manual review."
    )
    st.rerun()

st.markdown("---")

# Bulk actions
bc1, bc2, bc3 = st.columns(3)
with bc1:
    if st.button("⏩ Skip all <10% changes as-is (no update)", help="Mark all filtered items with <10% change as 'rejected / keep current'."):
        skipped = 0
        for w in filtered:
            if abs(w["change_pct"]) < 10 and w["prior_action"] is None:
                decisions[w["ingredient"]] = {
                    "action": "reject",
                    "kept_price": w["current_price"],
                    "timestamp": datetime.now().isoformat(),
                }
                skipped += 1
        save_decisions(decisions)
        st.success(f"Marked {skipped} items as rejected (kept current).")
        st.rerun()

with bc2:
    if st.button("📦 Apply all accepted decisions to canonical_price_list.json"):
        backup = CANONICAL_PRICE_FILE.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(CANONICAL_PRICE_FILE, backup)
        canon = load_json(CANONICAL_PRICE_FILE)
        applied = 0
        for item in canon.get("items", []):
            d = decisions.get(item["ingredient"])
            if d and d.get("action") == "accept" and d.get("accepted_price"):
                item["price_per_unit"] = d["accepted_price"]
                item["_last_refreshed"] = d.get("timestamp")
                applied += 1
        canon["generated_date"] = datetime.now().date().isoformat()
        save_json(CANONICAL_PRICE_FILE, canon)
        st.cache_data.clear()
        st.success(f"Applied {applied} price updates. Backup: `{os.path.basename(backup)}`")
        st.rerun()

with bc3:
    if st.button("🧹 Clear all saved decisions (start over)"):
        save_decisions({})
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# Per-item cards
for w in filtered[:50]:  # batch of 50 per page
    key = w["ingredient"]
    change_color = "red" if w["change_pct"] > 10 else ("orange" if w["change_pct"] > 5 else ("green" if w["change_pct"] < -5 else "gray"))

    with st.container(border=True):
        h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
        with h1:
            st.markdown(f"**{w['ingredient']}**  \n_UOM: {w['canonical_uom']} | Supplier: {w['canonical_item'].get('supplier', '–')}_")
            if w["prior_action"]:
                st.caption(f"🔖 Previous decision: **{w['prior_action']}** ({w.get('prior_price') or w['canonical_item'].get('price_per_unit')})")
        with h2:
            st.metric("Current", f"{w['current_price']:.4f}")
        with h3:
            st.metric("Proposed", f"{w['proposed_price']:.4f}",
                      f"{w['change_pct']:+.1f}%", delta_color="off")
        with h4:
            unit_ok = "✅" if w["unit_match"] else "⚠️"
            st.caption(f"{unit_ok} Unit match: {w['unit_match']}")

        # Observations table — enrich with parsed pack size from item_name
        obs_rows = []
        detected_packs = []  # collect for auto-suggestion
        for o in w["observations"]:
            parsed_pack, pack_explain = parse_pack_from_name(o.get("item_name", ""))
            pack_from_ocr = o.get("pack_size")
            # Prefer OCR-captured pack_size if present, else the name-parsed one
            effective_pack = pack_from_ocr or parsed_pack
            if effective_pack:
                detected_packs.append(effective_pack)
            obs_rows.append({
                "Date": o.get("date", ""),
                "Supplier": (o.get("supplier") or "")[:25],
                "Item as invoiced": (o.get("item_name") or "")[:45],
                "Qty": o.get("quantity"),
                "Unit (raw)": o.get("unit_raw"),
                "Unit price": f"{o.get('unit_price', 0):.4f}",
                "Total": o.get("total_price"),
                "Pack detected": effective_pack or "–",
                "Pack logic": pack_explain or "(none detected)",
            })
        obs_df = pd.DataFrame(obs_rows)
        st.dataframe(obs_df, use_container_width=True, hide_index=True)

        # Suggested pack: most-common detected pack size across the 3 observations
        if detected_packs:
            from collections import Counter
            suggested_pack = Counter(detected_packs).most_common(1)[0][0]
        else:
            suggested_pack = 1

        # --- Action row 1: Accept the proposed price as-is, or reject ---
        a1, a2 = st.columns(2)
        with a1:
            if st.button(f"✅ Accept proposed ({w['proposed_price']:.4f})", key=f"acc_{key}", type="primary", use_container_width=True):
                decisions[key] = {
                    "action": "accept",
                    "accepted_price": w["proposed_price"],
                    "old_price": w["current_price"],
                    "change_pct": w["change_pct"],
                    "timestamp": datetime.now().isoformat(),
                }
                save_decisions(decisions)
                st.rerun()
        with a2:
            if st.button(f"❌ Reject (keep current {w['current_price']:.4f})", key=f"rej_{key}", use_container_width=True):
                decisions[key] = {
                    "action": "reject",
                    "kept_price": w["current_price"],
                    "timestamp": datetime.now().isoformat(),
                }
                save_decisions(decisions)
                st.rerun()

        # --- Action row 2: Pack-aware conversion OR custom price ---
        st.caption(f"Convert observed price → per-{w['canonical_uom'] or 'unit'} rate, or type a custom price")
        p1, p2, p3, p4 = st.columns([1.2, 1.2, 1.2, 1.5])
        with p1:
            pack_case_price = st.number_input(
                "Case/pack price",
                min_value=0.0,
                value=float(w["proposed_price"]),
                step=0.01,
                key=f"case_{key}",
                help="e.g. 40 AED (price supplier charges for the whole carton)",
            )
        with p2:
            pack_size = st.number_input(
                "Pack size (pcs in pack)",
                min_value=1,
                value=int(suggested_pack),
                step=1,
                key=f"pack_{key}",
                help=f"Auto-detected from item name: {suggested_pack}. Override if wrong.",
            )
        with p3:
            per_unit_calc = pack_case_price / max(pack_size, 1)
            st.metric(f"Per-{w['canonical_uom'] or 'unit'}", f"{per_unit_calc:.4f}",
                      help="Calculated: case_price ÷ pack_size")
        with p4:
            if st.button(f"💾 Save {per_unit_calc:.4f}", key=f"save_calc_{key}", use_container_width=True):
                decisions[key] = {
                    "action": "accept_pack_converted",
                    "accepted_price": round(per_unit_calc, 4),
                    "case_price_used": float(pack_case_price),
                    "pack_size_used": int(pack_size),
                    "old_price": w["current_price"],
                    "change_pct": round((per_unit_calc - w["current_price"]) / w["current_price"] * 100, 1) if w["current_price"] else 0,
                    "timestamp": datetime.now().isoformat(),
                }
                save_decisions(decisions)
                st.rerun()
