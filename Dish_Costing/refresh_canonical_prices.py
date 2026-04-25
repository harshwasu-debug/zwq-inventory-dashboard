"""Refresh canonical_price_list.json prices from the invoice observation ledger.

Pipeline:
  1. For each canonical ingredient, gather TRUSTED observations:
       - match_method == "live_confirm"  (price already normalized via confirm_invoice)
       - OR pack_size + case_price present (derive per-canonical-unit)
       - OR observation unit_normalized matches the canonical uom
  2. Aggregate:
       - median of last 5 trusted obs in last 90d
       - fallback: most-recent trusted obs in last 365d
       - else: keep current canonical price (no change)
  3. Stamp `latest_price_source` provenance on each updated item.
  4. Default mode is PREVIEW (writes report CSV, no canonical mutation).
     Pass --apply to write changes (with timestamped backup).

Usage:
    python refresh_canonical_prices.py            # preview only
    python refresh_canonical_prices.py --apply    # apply changes
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import statistics
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_FILE = os.path.join(ROOT, "Dish_Costing", "canonical_price_list.json")
OBSERVATIONS_FILE = os.path.join(ROOT, "Invoices", "price_observations.json")
REPORT_CSV = os.path.join(ROOT, "Dish_Costing", "price_refresh_report.csv")

WINDOW_RECENT_DAYS = 90
WINDOW_FALLBACK_DAYS = 365
RECENT_N = 5
SIGNIFICANT_CHANGE_PCT = 5.0  # for highlighting in report only

# Sanity bounds: a candidate price is "ok" if within these multiples of the
# current canonical price. Outside this band = unit mismatch suspicion (e.g.
# case price being read as unit price). Suspicious items are reported but NOT
# auto-applied — user reviews in CSV.
SANITY_LOWER = 0.4
SANITY_UPPER = 2.5


def _parse_date(s: str) -> Optional[dt.date]:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _units_align(unit_normalized: str, canonical_uom: str) -> bool:
    unit_n = (unit_normalized or "").lower().strip()
    canon = (canonical_uom or "").lower().strip()
    if not unit_n or not canon:
        return False
    return (
        (canon == "kg" and unit_n in {"kg", "kgs"})
        or (canon == "l" and unit_n in {"l", "ltr", "litre"})
        or (canon == "piece" and unit_n in {"piece", "pc", "pcs", "pieces", "nos", "each"})
    )


def _is_candidate(obs: dict, canonical_uom: str) -> bool:
    """An observation is a candidate for refresh if its price could plausibly map
    to canonical_uom. Sanity bounds (vs current canonical price) are applied later
    on the AGGREGATE candidate, not per-observation."""
    if obs.get("match_method") == "live_confirm":
        return True
    pack = obs.get("pack_size")
    case = obs.get("case_price")
    if pack and case and pack > 0:
        return True
    return _units_align(obs.get("unit_normalized") or "", canonical_uom)


def _normalized_price(obs: dict, canonical_uom: str) -> Optional[float]:
    """Return per-canonical-unit price for a trusted observation, or None."""
    if obs.get("match_method") == "live_confirm":
        p = obs.get("unit_price")
        return float(p) if p and p > 0 else None
    pack = obs.get("pack_size")
    case = obs.get("case_price")
    if pack and case and pack > 0:
        return round(float(case) / float(pack), 4)
    p = obs.get("unit_price")
    return float(p) if p and p > 0 else None


def compute_refresh(observations: dict, canonical_items: list, today: dt.date):
    """Return list of refresh-decision dicts (one per canonical item)."""
    decisions = []
    for item in canonical_items:
        name = item["ingredient"]
        canon_uom = item.get("uom", "")
        old_price = item.get("price_per_unit") or 0
        entry = observations.get(name) or {}
        all_obs = entry.get("observations") or []

        trusted = []
        for o in all_obs:
            d = _parse_date(o.get("date"))
            if not d:
                continue
            if not _is_candidate(o, canon_uom):
                continue
            p = _normalized_price(o, canon_uom)
            if not p or p <= 0:
                continue
            trusted.append({"date": d, "price": p, "supplier": o.get("supplier_slug") or o.get("supplier") or ""})

        trusted.sort(key=lambda x: x["date"], reverse=True)

        recent = [t for t in trusted if (today - t["date"]).days <= WINDOW_RECENT_DAYS][:RECENT_N]
        fallback = [t for t in trusted if (today - t["date"]).days <= WINDOW_FALLBACK_DAYS]

        if len(recent) >= 2:
            new_price = round(statistics.median(t["price"] for t in recent), 4)
            basis = f"median_of_{len(recent)}_in_{WINDOW_RECENT_DAYS}d"
            used = recent
        elif recent:
            new_price = round(recent[0]["price"], 4)
            basis = "single_recent"
            used = recent
        elif fallback:
            new_price = round(fallback[0]["price"], 4)
            basis = f"most_recent_in_{WINDOW_FALLBACK_DAYS}d"
            used = [fallback[0]]
        else:
            decisions.append({
                "ingredient": name, "uom": canon_uom, "old_price": old_price,
                "new_price": old_price, "change_pct": 0.0, "basis": "no_trusted_obs",
                "sanity": "n/a",
                "n_used": 0, "latest_date": "", "latest_supplier": "",
                "all_obs_count": len(all_obs), "action": "skip",
            })
            continue

        change_pct = round((new_price - old_price) / old_price * 100, 2) if old_price > 0 else None

        # Sanity gate: if the new price is wildly off the existing canonical, it's
        # almost certainly a unit mismatch (case price vs unit price). Flag it.
        if old_price > 0:
            ratio = new_price / old_price
            if ratio < SANITY_LOWER or ratio > SANITY_UPPER:
                sanity = "suspicious"
            else:
                sanity = "ok"
        else:
            # Old price is 0 — no anchor. Mark unverified so user reviews.
            sanity = "unverified"

        if abs(new_price - old_price) <= 0.0001:
            action = "no_change"
        elif sanity == "ok":
            action = "update"
        else:
            action = "review"  # not auto-applied; user must confirm

        decisions.append({
            "ingredient": name,
            "uom": canon_uom,
            "old_price": round(old_price, 4),
            "new_price": new_price,
            "change_pct": change_pct,
            "sanity": sanity,
            "basis": basis,
            "n_used": len(used),
            "latest_date": used[0]["date"].isoformat(),
            "latest_supplier": used[0]["supplier"],
            "all_obs_count": len(all_obs),
            "action": action,
        })
    return decisions


def write_report(decisions: list, out_path: str):
    fields = ["action", "sanity", "ingredient", "uom", "old_price", "new_price", "change_pct",
              "basis", "n_used", "latest_date", "latest_supplier", "all_obs_count"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        order = {"update": 0, "review": 1, "no_change": 2, "skip": 3}
        for d in sorted(decisions, key=lambda x: (order.get(x["action"], 9),
                                                  -abs(x.get("change_pct") or 0))):
            w.writerow({k: d.get(k, "") for k in fields})


def apply_changes(canonical: dict, decisions: list, today: dt.date) -> int:
    by_name = {d["ingredient"]: d for d in decisions}
    applied = 0
    for item in canonical.get("items", []):
        d = by_name.get(item["ingredient"])
        if not d or d["action"] != "update":
            continue
        item["price_per_unit"] = d["new_price"]
        item["latest_price_source"] = {
            "refreshed_at": today.isoformat(),
            "basis": d["basis"],
            "n_obs_used": d["n_used"],
            "latest_obs_date": d["latest_date"],
            "latest_supplier": d["latest_supplier"],
            "previous_price": d["old_price"],
        }
        applied += 1
    canonical["_last_price_refresh"] = {
        "at": today.isoformat(),
        "items_updated": applied,
    }
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes to canonical_price_list.json (default: preview only)")
    args = ap.parse_args()

    canonical = json.load(open(CANONICAL_FILE, encoding="utf-8"))
    observations = json.load(open(OBSERVATIONS_FILE, encoding="utf-8"))

    today = dt.date.today()
    decisions = compute_refresh(observations, canonical.get("items", []), today)

    by_action = {}
    for d in decisions:
        by_action[d["action"]] = by_action.get(d["action"], 0) + 1

    write_report(decisions, REPORT_CSV)

    print(f"Canonical items: {len(canonical.get('items', []))}")
    print(f"  update    : {by_action.get('update', 0)}  (auto-applied: passed sanity)")
    print(f"  review    : {by_action.get('review', 0)}  (suspicious / unverified — needs manual approval)")
    print(f"  no_change : {by_action.get('no_change', 0)}")
    print(f"  skip      : {by_action.get('skip', 0)} (no candidate obs)")
    print(f"\nReport: {REPORT_CSV}")

    significant = [d for d in decisions
                   if d["action"] == "update"
                   and d.get("change_pct") is not None
                   and abs(d["change_pct"]) >= SIGNIFICANT_CHANGE_PCT]
    if significant:
        print(f"\n{len(significant)} items changed by >= {SIGNIFICANT_CHANGE_PCT}%:")
        for d in sorted(significant, key=lambda x: -abs(x["change_pct"]))[:15]:
            print(f"  {d['change_pct']:+7.1f}%  {d['ingredient']:<40s} "
                  f"{d['old_price']:>8.2f} -> {d['new_price']:<8.2f} ({d['basis']}, n={d['n_used']})")

    if not args.apply:
        print("\nPreview only. Re-run with --apply to write changes.")
        return

    backup = CANONICAL_FILE.replace(".json", f"_backup_{today.strftime('%Y%m%d')}-refresh.json")
    shutil.copy2(CANONICAL_FILE, backup)
    print(f"\nBackup: {backup}")

    n = apply_changes(canonical, decisions, today)
    with open(CANONICAL_FILE, "w", encoding="utf-8") as f:
        json.dump(canonical, f, indent=2, ensure_ascii=False)
    print(f"Applied: {n} price updates written to {CANONICAL_FILE}")


if __name__ == "__main__":
    main()
