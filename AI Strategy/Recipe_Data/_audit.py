#!/usr/bin/env python3
"""
ZwQ Recipe Data Drift Audit
Runs schema integrity checks against all *.json files in this directory.
Exit code: 0 = clean, 1 = drift detected.

Usage: python _audit.py [--verbose]
"""
import os, json, sys

CANON = os.path.dirname(os.path.abspath(__file__))
EXPECTED_TOP = {"schema_version", "source_file", "extracted_at", "last_updated", "recipe_count", "methodology", "changelog", "pending_decisions", "recipes"}
ALT_BRAND = {"brand", "dataset"}
EXPECTED_RECIPE = {"recipe_number", "recipe_name", "brand", "category", "ingredients", "packaging", "allergens", "calories_kcal", "yield", "portion_size", "serves", "method", "plating", "notes"}
EXPECTED_ING = {"name", "quantity", "unit", "wastage_pct", "notes"}
ALLERGEN_VOCAB = {"Celery", "Gluten", "Crustaceans", "Fish", "Eggs", "Lupin", "Molluscs", "Mustard", "Nuts", "Peanuts", "Sesame", "Soya", "Sulphites", "Sugared drink", "Dairy", "Lentils", "NO_ALLERGENS"}

verbose = "--verbose" in sys.argv
files = sorted(f for f in os.listdir(CANON) if f.endswith(".json") and not f.startswith("_"))

drift_count = 0
results = []

for fname in files:
    p = os.path.join(CANON, fname)
    try:
        d = json.load(open(p, "r", encoding="utf-8"))
    except Exception as e:
        results.append((fname, ["JSON PARSE ERROR: " + str(e)], {}))
        drift_count += 1
        continue

    flags = []
    top = set(d.keys())
    if EXPECTED_TOP - top:
        flags.append("missing top keys: " + str(sorted(EXPECTED_TOP - top)))
    if not (top & ALT_BRAND):
        flags.append("missing brand or dataset key")

    m = d.get("methodology")
    if not isinstance(m, dict) or not all(k in m for k in ("allergens", "calories", "wastage_pct")):
        flags.append("methodology block invalid")

    if not d.get("changelog"):
        flags.append("no changelog")

    null_k = bad_ing = bad_pkg = 0
    rogue_set = set()
    rec_key_missing = set()
    for r in d.get("recipes", []):
        if not isinstance(r, dict):
            continue
        rk = set(r.keys())
        rec_key_missing |= (EXPECTED_RECIPE - rk)
        if r.get("calories_kcal") is None:
            null_k += 1
        a = r.get("allergens") or []
        if isinstance(a, list):
            for t in a:
                if t not in ALLERGEN_VOCAB:
                    rogue_set.add(t)
        for ing in r.get("ingredients") or []:
            if isinstance(ing, dict) and set(ing.keys()) != EXPECTED_ING:
                bad_ing += 1
                break
        for ing in r.get("packaging") or []:
            if isinstance(ing, dict) and set(ing.keys()) != EXPECTED_ING:
                bad_pkg += 1
                break

    if rec_key_missing:
        flags.append("per-recipe keys missing: " + str(sorted(rec_key_missing)))
    if rogue_set:
        flags.append("rogue allergens: " + str(sorted(rogue_set)))
    if bad_ing:
        flags.append(str(bad_ing) + " recipes with non-canonical ingredient shape")
    if bad_pkg:
        flags.append(str(bad_pkg) + " recipes with non-canonical packaging shape")

    if flags:
        drift_count += 1

    meta = {"recipes": len(d.get("recipes", [])), "null_kcal": null_k, "open_pds": len(d.get("pending_decisions", []))}
    results.append((fname, flags, meta))

print("ZwQ Recipe Data Drift Audit -- " + str(len(files)) + " files")
print("=" * 60)
for fname, flags, meta in results:
    if flags:
        print("  [DRIFT] " + fname)
        for fl in flags:
            print("          - " + fl)
    elif verbose:
        print("  [OK]    " + fname.ljust(40) + " " + str(meta.get("recipes", 0)).rjust(4) + " recipes, " + str(meta.get("null_kcal", 0)) + " null kcal, " + str(meta.get("open_pds", 0)) + " open PDs")

if drift_count == 0:
    print("\nAll files clean. Schema integrity verified.")
    sys.exit(0)
else:
    print("\n" + str(drift_count) + " file(s) with drift. Fix before proceeding.")
    sys.exit(1)
