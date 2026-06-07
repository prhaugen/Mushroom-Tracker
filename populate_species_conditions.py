"""
One-time script: populate species growing conditions.

Steps:
  1. Seed temp, humidity, CO2 from agent_config for the ~22 known species.
  2. Regex-extract fruiting temp (and humidity where present) from
     structured description lines like:
       "Colonization/Fruiting Temperatures: 65-75F/55-70F, Humidity: 85-95%"
  3. Batch remaining descriptions through Claude to extract any temperature
     ranges mentioned in free text. Humidity and CO2 returned only if
     explicitly stated.

Run: python populate_species_conditions.py [--sandbox]
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

import anthropic
from agent_config import SPECIES_TIMELINES

PROD_DB    = Path(__file__).parent / "mushroom_data.db"
SANDBOX_DB = Path(__file__).parent / "mushroom_data_sandbox.db"

# ── Regex patterns ────────────────────────────────────────────────────────────
# "Colonization/Fruiting Temperatures: 70-80F/55-70F"
#   → colonization = groups 1,2   fruiting = groups 3,4
_TEMP_COL_FRUIT = re.compile(
    r"Colonization/Fruiting Temperatures?:\s*([\d.]+)-([\d.]+)F/([\d.]+)-([\d.]+)F", re.I
)
# "Fruiting Temperature: 55-70F"  →  group 1,2
_TEMP_FRUIT_ONLY = re.compile(
    r"Fruiting Temperatures?:\s*([\d.]+)-([\d.]+)F", re.I
)
# "Humidity: 85-95%"  →  group 1,2
_HUMIDITY = re.compile(r"Humidity:\s*([\d.]+)-([\d.]+)%", re.I)


# ── Step 1: agent_config seed ─────────────────────────────────────────────────

_LIKE_MAP = [
    ("%lion%mane%",    "lions mane"),
    ("%chestnut%",     "chestnut"),
    ("enoki%",         "enoki"),
    ("%pioppino%",     "pioppino"),
    ("%elm%oyster%",   "elm oyster"),
    ("cordyceps%",     "cordyceps"),
    ("%black%oyster%", "black oyster"),
    ("%white%oyster%", "white oyster"),
    ("%snow%oyster%",  "snow oyster"),
]

def _upsert_conditions(c, where_clause, params, cfg_key):
    cfg = SPECIES_TIMELINES[cfg_key]
    ft_lo, ft_hi = cfg.get("fruiting_temp_f",      (None, None))
    ct_lo, ct_hi = cfg.get("colonization_temp_f",  (None, None))
    h_lo,  h_hi  = cfg.get("fruiting_humidity_rh", (None, None))
    c_lo,  c_hi  = cfg.get("fruiting_co2_ppm",     (None, None))
    c.execute(f"""UPDATE species_db SET
        fruiting_temp_lo_f     = COALESCE(fruiting_temp_lo_f,     ?),
        fruiting_temp_hi_f     = COALESCE(fruiting_temp_hi_f,     ?),
        colonization_temp_lo_f = COALESCE(colonization_temp_lo_f, ?),
        colonization_temp_hi_f = COALESCE(colonization_temp_hi_f, ?),
        humidity_lo_rh         = COALESCE(humidity_lo_rh,         ?),
        humidity_hi_rh         = COALESCE(humidity_hi_rh,         ?),
        co2_lo_ppm             = COALESCE(co2_lo_ppm,             ?),
        co2_hi_ppm             = COALESCE(co2_hi_ppm,             ?)
        WHERE {where_clause}""",
        (ft_lo, ft_hi, ct_lo, ct_hi, h_lo, h_hi, c_lo, c_hi, *params))

def seed_from_agent_config(conn):
    c = conn.cursor()
    for name, _ in SPECIES_TIMELINES.items():
        _upsert_conditions(c, "lower(common_name)=?", (name,), name)
    for pattern, cfg_key in _LIKE_MAP:
        _upsert_conditions(c, "lower(common_name) LIKE ?", (pattern,), cfg_key)
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL"
    ).fetchone()[0]
    print(f"  After agent_config seed: {n} entries have temp data")


# ── Step 2: regex extraction from structured descriptions ──────────────────────

def extract_from_descriptions_regex(conn):
    c = conn.cursor()
    rows = conn.execute(
        "SELECT id, common_name, description FROM species_db "
        "WHERE description IS NOT NULL AND description != ''"
    ).fetchall()

    updated = 0
    for r in rows:
        d = r["description"]
        ft_lo = ft_hi = ct_lo = ct_hi = h_lo = h_hi = None

        m = _TEMP_COL_FRUIT.search(d)
        if m:
            ct_lo, ct_hi = float(m.group(1)), float(m.group(2))
            ft_lo, ft_hi = float(m.group(3)), float(m.group(4))
        else:
            m2 = _TEMP_FRUIT_ONLY.search(d)
            if m2:
                ft_lo, ft_hi = float(m2.group(1)), float(m2.group(2))

        mh = _HUMIDITY.search(d)
        if mh:
            h_lo, h_hi = float(mh.group(1)), float(mh.group(2))

        if ft_lo is None and ct_lo is None and h_lo is None:
            continue

        c.execute("""UPDATE species_db SET
            fruiting_temp_lo_f     = COALESCE(fruiting_temp_lo_f,     ?),
            fruiting_temp_hi_f     = COALESCE(fruiting_temp_hi_f,     ?),
            colonization_temp_lo_f = COALESCE(colonization_temp_lo_f, ?),
            colonization_temp_hi_f = COALESCE(colonization_temp_hi_f, ?),
            humidity_lo_rh         = COALESCE(humidity_lo_rh,         ?),
            humidity_hi_rh         = COALESCE(humidity_hi_rh,         ?)
            WHERE id=?""",
            (ft_lo, ft_hi, ct_lo, ct_hi, h_lo, h_hi, r["id"]))
        if c.rowcount:
            updated += 1

    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL"
    ).fetchone()[0]
    print(f"  After regex extraction: {n} entries have temp data ({updated} new)")


# ── Step 3: Claude batch extraction for remaining descriptions ─────────────────

_SYSTEM = """\
Extract mushroom growing conditions from description text.
Return a JSON array — one object per species — using exactly this shape:
{"id":<int>,
 "fruiting_temp_lo_f":<num|null>,"fruiting_temp_hi_f":<num|null>,
 "colonization_temp_lo_f":<num|null>,"colonization_temp_hi_f":<num|null>,
 "humidity_lo_rh":<num|null>,"humidity_hi_rh":<num|null>,
 "co2_lo_ppm":<num|null>,"co2_hi_ppm":<num|null>}

Rules:
- Only extract values explicitly stated. Return null for anything not mentioned.
- Distinguish fruiting temp from colonization temp when both are present.
- Temperatures must be Fahrenheit. Convert from Celsius if needed (C*9/5+32).
- Humidity values are % RH (e.g. "85-95%" gives 85, 95).
- CO2 in ppm. Return null unless a numeric ppm range is stated.
- Output only the JSON array, no markdown, no commentary.\
"""

def extract_from_descriptions_claude(conn):
    rows = conn.execute("""
        SELECT id, common_name, description FROM species_db
        WHERE description IS NOT NULL AND description != ''
          AND fruiting_temp_lo_f IS NULL
        ORDER BY id
    """).fetchall()

    if not rows:
        print("  No entries need Claude extraction.")
        return

    print(f"  Sending {len(rows)} descriptions to Claude (Haiku)…")
    client = anthropic.Anthropic()
    c = conn.cursor()
    BATCH = 20
    total_updated = 0

    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        user_text = "\n\n".join(
            f"ID: {r['id']}\nName: {r['common_name']}\nDescription: {r['description']}"
            for r in batch
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=[{"type": "text", "text": _SYSTEM,
                          "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_text}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            results = json.loads(text)
        except Exception as e:
            print(f"  Batch {i//BATCH+1} error: {e}")
            continue

        batch_updated = 0
        for r in results:
            ft_lo = r.get("fruiting_temp_lo_f")
            ft_hi = r.get("fruiting_temp_hi_f")
            ct_lo = r.get("colonization_temp_lo_f")
            ct_hi = r.get("colonization_temp_hi_f")
            h_lo  = r.get("humidity_lo_rh")
            h_hi  = r.get("humidity_hi_rh")
            c_lo  = r.get("co2_lo_ppm")
            c_hi  = r.get("co2_hi_ppm")
            if any(v is not None for v in (ft_lo, ft_hi, ct_lo, ct_hi, h_lo, h_hi, c_lo, c_hi)):
                c.execute("""UPDATE species_db SET
                    fruiting_temp_lo_f     = COALESCE(fruiting_temp_lo_f,     ?),
                    fruiting_temp_hi_f     = COALESCE(fruiting_temp_hi_f,     ?),
                    colonization_temp_lo_f = COALESCE(colonization_temp_lo_f, ?),
                    colonization_temp_hi_f = COALESCE(colonization_temp_hi_f, ?),
                    humidity_lo_rh         = COALESCE(humidity_lo_rh,         ?),
                    humidity_hi_rh         = COALESCE(humidity_hi_rh,         ?),
                    co2_lo_ppm             = COALESCE(co2_lo_ppm,             ?),
                    co2_hi_ppm             = COALESCE(co2_hi_ppm,             ?)
                    WHERE id=?""",
                    (ft_lo, ft_hi, ct_lo, ct_hi, h_lo, h_hi, c_lo, c_hi, r["id"]))
                batch_updated += c.rowcount

        conn.commit()
        total_updated += batch_updated
        print(f"  Batch {i//BATCH+1}/{-(-len(rows)//BATCH)}: "
              f"{len(batch)} sent, {batch_updated} updated")

    n = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL"
    ).fetchone()[0]
    print(f"  After Claude extraction: {n} entries have temp data "
          f"({total_updated} new)")


# ── Step 4: researched species seeds ─────────────────────────────────────────

# Specific species by scientific name (researched values)
_SPECIFIC_SEEDS = [
    # (scientific_name,              t_lo, t_hi, h_lo, h_hi, c_lo, c_hi)
    ("Tremella fuciformis",           64,  75,  90, 100, None, None),
    ("Hypsizygus ulmarius",           50,  65,  85,  95, None, 1500),
    ("Lignosus rhinocerus",           77,  86,  70,  90, None, None),
    ("Pleurotus dryinus",             55,  68,  85,  95,  400,  800),
    ("Pleurotus spodoleucus",         60,  72,  85,  95,  400,  800),
    ("Pleurotus cystidiosus",         68,  82,  85,  95,  400,  800),
    ("Lentinus crinitus",             75,  86,  80,  90, None, None),
    ("Lentinus lepideus",             55,  70,  80,  90, None, None),
    ("Schizophyllum commune",         65,  77,  80,  95, None,  800),
    ("Kuehneromyces mutabilis",       50,  60,  80,  90, None, None),
    ("Hericium cirrhatum",            60,  75,  85,  95,  400, 1500),
    ("Lepista nuda",                  45,  60,  85,  95, None, None),
    ("Clitocybe sordida",             50,  65,  85,  95, None, None),
    ("Oudemansiella canarii",         72,  82,  80,  90, None, None),
    ("Macrocybe titans",              77,  86,  80,  90, None, None),
    ("Polyporus umbellatus",          65,  75,  85,  95, None, None),
    ("Laetiporus sulphureus",         65,  77,  80,  90, None, None),
    ("Laetiporus conifericola",       65,  77,  80,  90, None, None),
    ("Laetiporus zonatus",            65,  77,  80,  90, None, None),
    ("Laetiporus gilbertsonii",       65,  77,  80,  90, None, None),
    ("Laetiporus cincinnatus",        65,  77,  80,  90, None, None),
    ("Agaricus bisporus",             55,  64,  85,  95,  800, 2000),
    ("Agaricus blazei",               64,  86,  80,  95, None, 2000),
    ("Agaricus subrufescens",         64,  86,  80,  95, None, 2000),
    ("Bondarzewia berkeleyi",         65,  77,  85,  95, None, None),
    ("Polyporus squamosus",           55,  70,  80,  90, None, None),
    ("Armillariella mellea",          45,  65,  80,  90, None, None),
    ("Armillaria mellea",             45,  65,  80,  90, None, None),
    ("Armillaria gallica",            45,  65,  80,  90, None, None),
    ("Armillaria nabsnona",           45,  65,  80,  90, None, None),
    ("Inonotus obliquus",             50,  68,  80,  90, None, None),
    ("Pluteus cervinus",              55,  72,  85,  90, None, None),
    ("Hypholoma capnoides",           50,  65,  85,  95, None, None),
    ("Hydnum repandum",               50,  65,  85,  95, None, None),
    ("Ganoderma applanatum",          65,  80,  85,  95, None, 1500),
    ("Fistulina hepatica",            55,  70,  80,  90, None, None),
    ("Agrocybe aegerita",             50,  65,  85,  95,  400,  800),
    ("Sparassis crispa",              55,  65,  85,  95, None, None),
    ("Phellinus linteus",             65,  80,  85,  95, None, None),
]

# Genus-level humidity + CO2 defaults for species that have temp but no humidity
_GENUS_HUMIDITY = [
    # (genus_prefix,  h_lo, h_hi, c_lo, c_hi)
    ("Pleurotus",      85,  95,  400,  800),
    ("Hericium",       85,  95,  400, 1500),
    ("Ganoderma",      85,  95,  400, 1500),
    ("Hypsizygus",     85,  95,  400,  800),
    ("Hypholoma",      85,  95,  400,  800),
    ("Agrocybe",       85,  95,  400,  800),
    ("Pholiota",       85,  95,  400,  800),
    ("Panellus",       80,  90,  400,  800),
    ("Lentinus",       80,  90,  400,  800),
    ("Sparassis",      85,  95,  400,  800),
    ("Phellinus",      85,  95,  400, 1500),
    ("Trametes",       80,  90,  400,  800),
    ("Fomitopsis",     80,  90,  400,  800),
    ("Laetiporus",     80,  90,  400,  800),
]

def seed_researched(conn):
    c = conn.cursor()
    updated = 0
    for sci, t_lo, t_hi, h_lo, h_hi, c_lo, c_hi in _SPECIFIC_SEEDS:
        c.execute("""UPDATE species_db SET
            fruiting_temp_lo_f      = COALESCE(fruiting_temp_lo_f,      ?),
            fruiting_temp_hi_f      = COALESCE(fruiting_temp_hi_f,      ?),
            humidity_lo_rh = COALESCE(humidity_lo_rh, ?),
            humidity_hi_rh = COALESCE(humidity_hi_rh, ?),
            co2_lo_ppm     = COALESCE(co2_lo_ppm,     ?),
            co2_hi_ppm     = COALESCE(co2_hi_ppm,     ?)
            WHERE scientific_name=?""",
            (t_lo, t_hi, h_lo, h_hi, c_lo, c_hi, sci))
        updated += c.rowcount
    for genus, h_lo, h_hi, c_lo, c_hi in _GENUS_HUMIDITY:
        c.execute("""UPDATE species_db SET
            humidity_lo_rh = COALESCE(humidity_lo_rh, ?),
            humidity_hi_rh = COALESCE(humidity_hi_rh, ?),
            co2_lo_ppm     = COALESCE(co2_lo_ppm,     ?),
            co2_hi_ppm     = COALESCE(co2_hi_ppm,     ?)
            WHERE scientific_name LIKE ? AND fruiting_temp_lo_f IS NOT NULL
              AND humidity_lo_rh IS NULL""",
            (h_lo, h_hi, c_lo, c_hi, f"{genus}%"))
        updated += c.rowcount
    # Blanket humidity default for any remaining cultivatable entries
    c.execute("""UPDATE species_db SET
        humidity_lo_rh = COALESCE(humidity_lo_rh, 85),
        humidity_hi_rh = COALESCE(humidity_hi_rh, 95)
        WHERE fruiting_temp_lo_f IS NOT NULL AND humidity_lo_rh IS NULL""")
    updated += c.rowcount
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE humidity_lo_rh IS NOT NULL"
    ).fetchone()[0]
    print(f"  After researched seed: {n} entries have humidity data ({updated} updates)")


# ── Step 5: CO2 fill ─────────────────────────────────────────────────────────

def seed_co2(conn):
    c = conn.cursor()

    def upd(where, params, lo, hi):
        c.execute(f"""UPDATE species_db SET
            co2_lo_ppm = COALESCE(co2_lo_ppm, ?),
            co2_hi_ppm = COALESCE(co2_hi_ppm, ?)
            WHERE {where}""", (lo, hi, *params))
        return c.rowcount

    # Shiitake strains (Lentinula spp.) share Shiitake's 400-1000 range
    upd("scientific_name LIKE ?", ("Lentinula%",), 400, 1000)
    # Name-miss fixes: Maitake listed as "Dancing Hens", Cordyceps militaris as "Scarlet Caterpillarclub"
    upd("scientific_name = ?", ("Grifola frondosa",), 400, 800)
    upd("scientific_name = ?", ("Cordyceps militaris",), 400, 800)
    # Tiger Milk Mushroom has unusually high CO2 tolerance
    upd("scientific_name = ?", ("Lignosus rhinocerus",), 400, 5000)
    # Horse Mushroom — also needs temp/humidity
    c.execute("""UPDATE species_db SET
        fruiting_temp_lo_f      = COALESCE(fruiting_temp_lo_f,      50),
        fruiting_temp_hi_f      = COALESCE(fruiting_temp_hi_f,      65),
        humidity_lo_rh = COALESCE(humidity_lo_rh, 85),
        humidity_hi_rh = COALESCE(humidity_hi_rh, 95),
        co2_lo_ppm     = COALESCE(co2_lo_ppm,     400),
        co2_hi_ppm     = COALESCE(co2_hi_ppm,     800)
        WHERE scientific_name = 'Agaricus arvensis'""")
    # Blanket 400-800 for everything else with temp but still no CO2
    upd("fruiting_temp_lo_f IS NOT NULL AND co2_lo_ppm IS NULL", (), 400, 800)

    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE co2_lo_ppm IS NOT NULL"
    ).fetchone()[0]
    all3 = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL "
        "AND humidity_lo_rh IS NOT NULL AND co2_lo_ppm IS NOT NULL"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM species_db").fetchone()[0]
    print(f"  Have CO2: {n}/{total}   All three: {all3}/{total}")


# ── Step 6: difficulty assignment ─────────────────────────────────────────────

_DIFFICULTY_RULES = [
    # Specific scientific name overrides (checked first)
    ("sci_exact", "Pleurotus eryngii",              "intermediate"),  # King Oyster
    ("sci_exact", "Cordyceps militaris",             "intermediate"),  # cultivatable on grain
    ("sci_exact", "Flammulina velutipes",            "intermediate"),  # Enoki, needs cold
    ("sci_exact", "Flammulina fennae",               "intermediate"),
    ("sci_exact", "Flammulina populicola",           "intermediate"),
    ("sci_exact", "Isaria farinosa",                 "advanced"),
    ("sci_exact", "Isaria tenuipes",                 "advanced"),
    ("sci_exact", "Tolypocladium ophioglossoides",   "advanced"),
    ("sci_exact", "Ustilago maydis",                 "intermediate"),
    # Beginner genera
    ("sci_like", "Pleurotus%",       "beginner"),
    ("sci_like", "Hericium%",        "beginner"),
    ("sci_like", "Auricularia%",     "beginner"),
    # Intermediate genera
    ("sci_like", "Lentinula%",       "intermediate"),
    ("sci_like", "Hypsizygus%",      "intermediate"),
    ("sci_like", "Pholiota%",        "intermediate"),
    ("sci_like", "Flammulina%",      "intermediate"),
    ("sci_like", "Agrocybe%",        "intermediate"),
    ("sci_like", "Volvariella%",     "intermediate"),
    ("sci_like", "Agaricus%",        "intermediate"),
    ("sci_like", "Stropharia%",      "intermediate"),
    ("sci_like", "Hypholoma%",       "intermediate"),
    ("sci_like", "Lepista%",         "intermediate"),
    ("sci_like", "Kuehneromyces%",   "intermediate"),
    ("sci_like", "Lentinus%",        "intermediate"),
    ("sci_like", "Laetiporus%",      "intermediate"),
    ("sci_like", "Calocybe%",        "intermediate"),
    ("sci_like", "Tremella%",        "intermediate"),
    ("sci_like", "Coprinellus%",     "intermediate"),
    ("sci_like", "Coprinus%",        "intermediate"),
    ("sci_like", "Calvatia%",        "intermediate"),
    ("sci_like", "Lycoperdon%",      "intermediate"),
    ("sci_like", "Macrocybe%",       "intermediate"),
    ("sci_like", "Panellus%",        "intermediate"),
    ("sci_like", "Pluteus%",         "intermediate"),
    ("sci_like", "Schizophyllum%",   "intermediate"),
    ("sci_like", "Termitomyces%",    "intermediate"),
    ("sci_like", "Oudemansiella%",   "intermediate"),
    ("sci_like", "Clavicorona%",     "intermediate"),
    ("sci_like", "Cyathus%",         "intermediate"),
    ("sci_like", "Clitocybe%",       "intermediate"),
    # Advanced genera
    ("sci_like", "Morchella%",       "advanced"),
    ("sci_like", "Ganoderma%",       "advanced"),
    ("sci_like", "Grifola%",         "advanced"),
    ("sci_like", "Trametes%",        "advanced"),
    ("sci_like", "Inonotus%",        "advanced"),
    ("sci_like", "Bondarzewia%",     "advanced"),
    ("sci_like", "Lignosus%",        "advanced"),
    ("sci_like", "Fomitopsis%",      "advanced"),
    ("sci_like", "Phellinus%",       "advanced"),
    ("sci_like", "Fistulina%",       "advanced"),
    ("sci_like", "Polyporus%",       "advanced"),
    ("sci_like", "Armillaria%",      "advanced"),
    ("sci_like", "Armillariella%",   "advanced"),
    ("sci_like", "Sparassis%",       "advanced"),
    ("sci_like", "Cantharellus%",    "advanced"),
    ("sci_like", "Polyozellus%",     "advanced"),
    ("sci_like", "Hydnum%",          "advanced"),
    ("sci_like", "Omphalotus%",      "advanced"),
    ("sci_like", "Cordyceps%",       "advanced"),
    ("sci_like", "Ophiocordyceps%",  "advanced"),
    ("sci_like", "Tolypocladium%",   "advanced"),
    ("sci_like", "Isaria%",          "advanced"),
    ("sci_like", "Xylaria%",         "advanced"),
    ("sci_like", "Pisolithus%",      "advanced"),
    ("sci_like", "Phallus%",         "advanced"),
    ("sci_like", "Annulohypoxylon%", "advanced"),
    ("sci_like", "Daedaleopsis%",    "advanced"),
    ("sci_like", "Meripilus%",       "advanced"),
    ("sci_like", "Piptoporus%",      "advanced"),
    ("sci_like", "Chlorociboria%",   "advanced"),
    ("sci_like", "Exidia%",          "advanced"),
    ("sci_like", "Megacollybia%",    "advanced"),
    ("sci_like", "Globiformes%",     "advanced"),
    ("sci_like", "Lenzites%",        "advanced"),
    ("sci_like", "Polycephalomyces%","advanced"),
    ("sci_like", "Aspergillus%",     "advanced"),
    # Common name fallbacks for entries with no scientific name
    ("common_like", "%oyster%",       "beginner"),
    ("common_like", "%shiitake%",     "intermediate"),
    ("common_like", "%enoki%",        "intermediate"),
    ("common_like", "%garlic scented%","intermediate"),
    ("common_like", "%macrocybe%",    "intermediate"),
    ("common_like", "%reishi%",       "advanced"),
    ("common_like", "%morel%",        "advanced"),
    ("common_like", "%chanterelle%",  "advanced"),
    ("common_like", "%maitake%",      "advanced"),
    ("common_like", "%turkey tail%",  "advanced"),
    ("common_like", "%chaga%",        "advanced"),
    ("common_like", "%cordyceps%",    "advanced"),
    ("common_like", "%polycephalomyces%", "advanced"),
]

def seed_difficulty(conn):
    c = conn.cursor()
    total = 0
    for match_type, pattern, diff in _DIFFICULTY_RULES:
        if match_type == "sci_exact":
            c.execute("UPDATE species_db SET difficulty=? WHERE scientific_name=? AND difficulty IS NULL",
                      (diff, pattern))
        elif match_type == "sci_like":
            c.execute("UPDATE species_db SET difficulty=? WHERE scientific_name LIKE ? AND difficulty IS NULL",
                      (diff, pattern))
        elif match_type == "common_like":
            c.execute("UPDATE species_db SET difficulty=? WHERE lower(common_name) LIKE ? AND difficulty IS NULL",
                      (diff, pattern))
        total += c.rowcount
    conn.commit()
    dist = {r[0]: r[1] for r in conn.execute(
        "SELECT difficulty, COUNT(*) FROM species_db GROUP BY difficulty"
    ).fetchall()}
    print(f"  Assigned {total} entries: "
          f"{dist.get('beginner',0)} beginner, "
          f"{dist.get('intermediate',0)} intermediate, "
          f"{dist.get('advanced',0)} advanced, "
          f"{dist.get(None,0)} unset")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()

    db_path = SANDBOX_DB if args.sandbox else PROD_DB
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    print(f"Database: {db_path.name}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    print("\nStep 1 — agent_config seed")
    seed_from_agent_config(conn)

    print("\nStep 2 — regex extraction from structured descriptions")
    extract_from_descriptions_regex(conn)

    print("\nStep 3 — Claude extraction for remaining descriptions")
    extract_from_descriptions_claude(conn)

    print("\nStep 4 — researched species seeds + genus-level humidity defaults")
    seed_researched(conn)

    print("\nStep 5 — CO2 fill for remaining cultivatable entries")
    seed_co2(conn)

    print("\nStep 6 — difficulty assignment")
    seed_difficulty(conn)

    total   = conn.execute("SELECT COUNT(*) FROM species_db").fetchone()[0]
    has_t   = conn.execute("SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL").fetchone()[0]
    has_h   = conn.execute("SELECT COUNT(*) FROM species_db WHERE humidity_lo_rh IS NOT NULL").fetchone()[0]
    has_co2 = conn.execute("SELECT COUNT(*) FROM species_db WHERE co2_lo_ppm IS NOT NULL").fetchone()[0]
    has_all = conn.execute(
        "SELECT COUNT(*) FROM species_db WHERE fruiting_temp_lo_f IS NOT NULL "
        "AND humidity_lo_rh IS NOT NULL AND co2_lo_ppm IS NOT NULL"
    ).fetchone()[0]

    print(f"\n-- Final ({'sandbox' if args.sandbox else 'prod'}) --")
    print(f"  Total entries:       {total}")
    print(f"  Have temp:           {has_t}")
    print(f"  Have humidity:       {has_h}")
    print(f"  Have CO2:            {has_co2}")
    print(f"  Have all three:      {has_all}")

    conn.close()


if __name__ == "__main__":
    main()
