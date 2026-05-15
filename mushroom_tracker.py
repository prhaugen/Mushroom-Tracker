"""
Mushroom Growing Tracker — CLI
Schema v2: batches, flushes, environment_logs, sales

Usage:
    python mushroom_tracker.py setup
    python mushroom_tracker.py status
    python mushroom_tracker.py batch add
    python mushroom_tracker.py batch list
    python mushroom_tracker.py batch update <id>
    python mushroom_tracker.py flush log <batch_id>
    python mushroom_tracker.py flush list
    python mushroom_tracker.py env log
    python mushroom_tracker.py env history
    python mushroom_tracker.py report
"""

import sqlite3
import argparse
import sys
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "mushroom_data.db"

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()
    RICH = True
except ImportError:
    RICH = False

SCHEMA_VERSION = "2"
STATUSES    = ["colonizing","colonized","pinning","fruiting","resting","done","contaminated","aborted"]
LIFECYCLE   = ["colonizing","colonized","pinning","fruiting","resting"]
SPAWN_TYPES = ["grain","sawdust","plug","liquid_culture","agar","other"]
STERIL_METHODS = ["pressure_cooker","autoclave","pasteurization","lime_treat","cold_water","none"]
DESTINATIONS   = ["farmers_market","restaurant","personal","wholesale","csa","other"]
SPECIES = [
    "Blue Oyster",
    "Pearl Oyster",
    "Pink Oyster",
    "Golden Oyster",
    "Elm Oyster",
    "White Oyster",
    "Black Oyster",
    "King Oyster",
    "Lions Mane",
    "Shiitake",
    "Chestnut",
    "Reishi",
    "Maitake",
    "Nameko",
    "Pioppino",
    "Enoki",
    "Cordyceps",
    "Turkey Tail",
    "Wine Cap",
    "Bunashimeji",
]

SPECIES_CODES = {s.lower(): code for s, code in [
    ("Blue Oyster",   "BO"),
    ("Pearl Oyster",  "PO"),
    ("Pink Oyster",   "PK"),
    ("Golden Oyster", "GO"),
    ("Elm Oyster",    "EO"),
    ("White Oyster",  "WO"),
    ("Black Oyster",  "BLK"),
    ("King Oyster",   "KO"),
    ("Lions Mane",    "LM"),
    ("Shiitake",      "SHI"),
    ("Chestnut",      "CH"),
    ("Reishi",        "REI"),
    ("Maitake",       "MAI"),
    ("Nameko",        "NAM"),
    ("Pioppino",      "PIO"),
    ("Enoki",         "ENO"),
    ("Cordyceps",     "COR"),
    ("Turkey Tail",   "TT"),
    ("Wine Cap",      "WC"),
    ("Bunashimeji",   "BUN"),
]}


def species_code(species: str) -> str:
    """Return a 2-4 char uppercase code for a species name."""
    key = species.strip().lower()
    if key in SPECIES_CODES:
        return SPECIES_CODES[key]
    words = key.split()
    code = "".join(w[0] for w in words if w)[:4].upper()
    return code or "XX"


def next_batch_label(conn, species: str) -> str:
    """Return the next sequential label for a species, e.g. BO-003."""
    code = species_code(species)
    rows = conn.execute(
        "SELECT label FROM batches WHERE label LIKE ?", (f"{code}-%",)
    ).fetchall()
    max_seq = 0
    for row in rows:
        parts = row["label"].split("-")
        if len(parts) == 2 and parts[1].isdigit():
            max_seq = max(max_seq, int(parts[1]))
    return f"{code}-{max_seq + 1:03d}"


def get_all_species(conn) -> list:
    """Return sorted union of built-in SPECIES list and any user-added custom species."""
    custom = [r[0] for r in conn.execute(
        "SELECT name FROM custom_species ORDER BY name"
    ).fetchall()]
    combined = sorted(set(SPECIES) | set(custom), key=str.casefold)
    return combined


def get_substrate_other_options(conn) -> list:
    """Return all previously saved substrate_other values for datalist suggestions."""
    return [r[0] for r in conn.execute(
        "SELECT value FROM custom_substrate_other ORDER BY value"
    ).fetchall()]


def get_spawn_source_options(conn) -> list:
    """Return all previously saved spawn source/supplier values for datalist suggestions."""
    return [r[0] for r in conn.execute(
        "SELECT value FROM custom_spawn_source ORDER BY value"
    ).fetchall()]


CHAMBER_TYPES  = [
    "Shotgun Fruiting Chamber (SGFC)",
    "Martha Tent",
    "Mono Tub",
    "Automated Grow Tent",
    "Grow Cabinet",
    "Modified Freezer / Refrigerator",
    "Fruiting Room",
    "Dedicated Grow Room",
    "Still Air Box (SAB)",
    "Incubation Chamber",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS _meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS chambers (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            name               TEXT NOT NULL,
            location           TEXT,
            chamber_type       TEXT,
            target_temp_f      REAL DEFAULT 72.0,
            target_humidity_rh REAL DEFAULT 90.0,
            notes              TEXT,
            created_at         TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS batches (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            chamber_id              INTEGER REFERENCES chambers(id),
            label                   TEXT NOT NULL,
            species                 TEXT NOT NULL,
            strain                  TEXT,
            dry_weight_g            REAL,
            moisture_pct            REAL,
            straw_pct               REAL DEFAULT 0,
            hardwood_pct            REAL DEFAULT 0,
            bran_pct                REAL DEFAULT 0,
            gypsum_pct              REAL DEFAULT 0,
            coco_pct                REAL DEFAULT 0,
            substrate_other         TEXT,
            steril_method           TEXT,
            steril_temp_f           REAL,
            steril_duration_min     INTEGER,
            inoculation_date        TEXT,
            spawn_type              TEXT,
            spawn_strain            TEXT,
            spawn_rate_pct          REAL,
            spawn_source            TEXT,
            spawn_lot               TEXT,
            colonization_start_date TEXT,
            colonization_end_date   TEXT,
            first_pin_date          TEXT,
            colonization_chamber_id INTEGER REFERENCES chambers(id),
            target_temp_f           REAL DEFAULT 72.0,
            target_humidity_rh      REAL DEFAULT 90.0,
            status                  TEXT DEFAULT 'colonizing',
            contamination_flag      INTEGER DEFAULT 0,
            contamination_type      TEXT,
            abort_flag              INTEGER DEFAULT 0,
            abort_date              TEXT,
            block_end_date          TEXT,
            total_flushes           INTEGER DEFAULT 0,
            total_yield_g           REAL DEFAULT 0.0,
            fruiting_start_date     TEXT,
            sourced_block           INTEGER DEFAULT 0,
            notes                   TEXT,
            created_at              TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS flushes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id       INTEGER REFERENCES batches(id),
            flush_number   INTEGER NOT NULL,
            pinning_date   TEXT,
            harvest_date   TEXT DEFAULT CURRENT_DATE,
            fresh_weight_g REAL NOT NULL,
            quality_rating INTEGER,
            notes          TEXT,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS environment_logs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            chamber_id          INTEGER REFERENCES chambers(id),
            batch_id            INTEGER REFERENCES batches(id),
            logged_at           TEXT DEFAULT CURRENT_TIMESTAMP,
            phase               TEXT DEFAULT 'fruiting',
            temp_f              REAL,
            humidity_rh         REAL,
            co2_ppm             REAL,
            fae_fan_cycles_day  INTEGER,
            light_hours         REAL,
            misting_count       INTEGER,
            notes               TEXT
        );
        CREATE TABLE IF NOT EXISTS custom_species (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS custom_substrate_other (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            value      TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS custom_spawn_source (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            value      TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS daily_briefings (
            briefing_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            briefing_date   TEXT NOT NULL UNIQUE,
            raw_json        TEXT NOT NULL,
            attention_count INTEGER DEFAULT 0,
            critical_count  INTEGER DEFAULT 0,
            generated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            triggered_by    TEXT DEFAULT 'scheduler'
        );
        CREATE TABLE IF NOT EXISTS sales (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id             INTEGER REFERENCES batches(id),
            flush_id             INTEGER REFERENCES flushes(id),
            sale_date            TEXT DEFAULT CURRENT_DATE,
            destination          TEXT,
            customer             TEXT,
            fresh_weight_sold_g  REAL,
            dried_weight_sold_g  REAL,
            price_per_lb         REAL,
            notes                TEXT,
            created_at           TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS batch_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id   INTEGER NOT NULL REFERENCES batches(id),
            body       TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS lc_lots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor      TEXT NOT NULL,
            species     TEXT NOT NULL,
            order_date  TEXT,
            lot_number  TEXT,
            media_type  TEXT,
            notes       TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS substrate_batches (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            date_prepared         TEXT,
            substrate_type        TEXT,
            dry_weight_g          REAL,
            moisture_pct          REAL,
            straw_pct             REAL DEFAULT 0,
            hardwood_pct          REAL DEFAULT 0,
            bran_pct              REAL DEFAULT 0,
            gypsum_pct            REAL DEFAULT 0,
            coco_pct              REAL DEFAULT 0,
            substrate_other       TEXT,
            steril_method         TEXT,
            steril_temp_f         REAL,
            steril_duration_min   INTEGER,
            cooldown_duration_min INTEGER,
            notes                 TEXT,
            created_at            TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS grain_jars (
            id                         INTEGER PRIMARY KEY AUTOINCREMENT,
            lc_lot_id                  INTEGER REFERENCES lc_lots(id),
            spawn_source               TEXT,
            species                    TEXT NOT NULL,
            inoculation_date           TEXT,
            full_colonization_date     TEXT,
            outcome                    TEXT,
            used_in_substrate_batch_id INTEGER REFERENCES substrate_batches(id),
            notes                      TEXT,
            created_at                 TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Non-destructive column additions for env_logs upgrade from v1
    existing = {r[1] for r in c.execute("PRAGMA table_info(environment_logs)")}
    for col, typedef in {
        "batch_id": "INTEGER REFERENCES batches(id)",
        "phase": "TEXT DEFAULT 'fruiting'",
        "fae_fan_cycles_day": "INTEGER",
        "light_hours": "REAL",
        "misting_count": "INTEGER",
    }.items():
        if col not in existing:
            c.execute(f"ALTER TABLE environment_logs ADD COLUMN {col} {typedef}")

    # Non-destructive column addition for sales — customer field
    existing_s = {r[1] for r in c.execute("PRAGMA table_info(sales)")}
    if "customer" not in existing_s:
        c.execute("ALTER TABLE sales ADD COLUMN customer TEXT")

    # Non-destructive column additions for chambers
    existing_c = {r[1] for r in c.execute("PRAGMA table_info(chambers)")}
    if "chamber_type" not in existing_c:
        c.execute("ALTER TABLE chambers ADD COLUMN chamber_type TEXT")

    # Non-destructive column additions for batches
    existing_b = {r[1] for r in c.execute("PRAGMA table_info(batches)")}
    for col, typedef in {
        "colonization_chamber_id": "INTEGER REFERENCES chambers(id)",
        "target_temp_f": "REAL DEFAULT 72.0",
        "target_humidity_rh": "REAL DEFAULT 90.0",
        "substrate_notes": "TEXT",
        "pinning_started_at": "TEXT",
        "fruiting_start_date": "TEXT",
        "sourced_block": "INTEGER DEFAULT 0",
        "block_end_date": "TEXT",
        "substrate_batch_id": "INTEGER REFERENCES substrate_batches(id)",
    }.items():
        if col not in existing_b:
            c.execute(f"ALTER TABLE batches ADD COLUMN {col} {typedef}")

    # Non-destructive column addition for batch_notes — edit support
    existing_bn = {r[1] for r in c.execute("PRAGMA table_info(batch_notes)")}
    if "updated_at" not in existing_bn:
        c.execute("ALTER TABLE batch_notes ADD COLUMN updated_at TEXT")

    # One-time migration: seed batch_notes from existing batch.notes fields
    migrated = {r[0] for r in c.execute("SELECT DISTINCT batch_id FROM batch_notes")}
    for row in c.execute("SELECT id, notes, created_at FROM batches WHERE notes IS NOT NULL AND notes != ''").fetchall():
        if row[0] not in migrated:
            c.execute("INSERT INTO batch_notes (batch_id, body, created_at) VALUES (?, ?, ?)",
                      (row[0], row[1], row[2]))

    conn.commit()

    version = c.execute("SELECT value FROM _meta WHERE key='schema_version'").fetchone()
    if not version:
        _migrate_v1(conn, c)
        c.execute("INSERT OR REPLACE INTO _meta VALUES ('schema_version',?)", (SCHEMA_VERSION,))
        conn.commit()

    conn.close()


def _migrate_v1(conn, c):
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "blocks" in tables:
        for b in [dict(r) for r in c.execute("SELECT * FROM blocks")]:
            c.execute("""INSERT OR IGNORE INTO batches
                (id,chamber_id,label,species,inoculation_date,colonization_end_date,
                 first_pin_date,status,total_flushes,total_yield_g,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (b["id"],b["chamber_id"],b["label"],b["species"],
                 b.get("inoculation_date"),b.get("colonization_date"),b.get("first_pin_date"),
                 b.get("status","colonizing"),b.get("total_flushes",0),
                 b.get("total_yield_g",0.0),b.get("notes"),b.get("created_at")))
        c.execute("ALTER TABLE blocks RENAME TO blocks_v1")
    if "harvests" in tables:
        for h in [dict(r) for r in c.execute("SELECT * FROM harvests")]:
            c.execute("""INSERT OR IGNORE INTO flushes
                (id,batch_id,flush_number,harvest_date,fresh_weight_g,notes,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (h["id"],h["block_id"],h["flush_number"],
                 h.get("harvested_at","")[:10],h["weight_g"],
                 h.get("notes"),h.get("harvested_at")))
        c.execute("ALTER TABLE harvests RENAME TO harvests_v1")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_since(date_str):
    if not date_str: return None
    try: return (date.today() - datetime.strptime(date_str[:10],"%Y-%m-%d").date()).days
    except ValueError: return None

def _time_ago(ts):
    try:
        mins = int((datetime.now() - datetime.strptime(ts[:19],"%Y-%m-%d %H:%M:%S")).total_seconds()/60)
        if mins < 60: return f"{mins}m ago"
        if mins < 1440: return f"{mins//60}h ago"
        return f"{mins//1440}d ago"
    except Exception: return ts[:16]

def bio_efficiency(total_fresh_g, dry_weight_g):
    if dry_weight_g and dry_weight_g > 0:
        return round(total_fresh_g / dry_weight_g * 100, 1)
    return None

def _ok(t):  print(f"[green]OK[/green] {t}") if RICH else print(f"[OK] {t}")
def _err(t): print(f"[red]ERR[/red] {t}") if RICH else print(f"[ERR] {t}")
def _info(t):
    if RICH: console.print(f"[cyan]>[/cyan] {t}")
    else: print(f"  {t}")
def _hdr(t):
    if RICH: console.print(Panel(f"[bold green]{t}[/bold green]", expand=False))
    else: print(f"\n{'='*50}\n  {t}\n{'='*50}")
def _ask(prompt, default=""):
    val = input(f"{prompt}{' ['+default+']' if default else ''}: ").strip()
    return val if val else default


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_setup(args):
    init_db()
    conn = get_db()
    existing = conn.execute("SELECT * FROM chambers").fetchall()
    if existing:
        for ch in existing: _info(f"  [{ch['id']}] {ch['name']} - {ch['location']}")
        if input("Add another? (y/n): ").strip().lower() != 'y':
            conn.close(); return
    _hdr("Set Up Chamber")
    name     = _ask("Chamber name","SGFC-1")
    location = _ask("Location","Basement")
    for i, ct in enumerate(CHAMBER_TYPES, 1): _info(f"  {i}. {ct}")
    ct_idx   = _ask("Chamber type # (optional)")
    ch_type  = CHAMBER_TYPES[int(ct_idx)-1] if ct_idx and ct_idx.isdigit() and 1 <= int(ct_idx) <= len(CHAMBER_TYPES) else None
    temp     = _ask("Default target temp F","72")
    humidity = _ask("Default target humidity %","90")
    notes    = _ask("Notes (optional)")
    conn.execute("INSERT INTO chambers(name,location,chamber_type,target_temp_f,target_humidity_rh,notes) VALUES(?,?,?,?,?,?)",
                 (name,location,ch_type,float(temp),float(humidity),notes or None))
    conn.commit(); conn.close()
    _ok(f"Chamber '{name}' created.")


def _primary_chamber(conn):
    chs = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    if not chs: _err("No chambers. Run setup."); sys.exit(1)
    if len(chs) == 1: return chs[0]
    for ch in chs: _info(f"  [{ch['id']}] {ch['name']}")
    cid = input("Chamber ID: ").strip()
    ch = conn.execute("SELECT * FROM chambers WHERE id=?",(cid,)).fetchone()
    if not ch: _err("Not found."); sys.exit(1)
    return ch


def cmd_batch_add(args):
    init_db(); conn = get_db()
    all_chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    _hdr("Add Batch")
    _info("Fruiting chamber:")
    chamber = _primary_chamber(conn)
    col_chamber_id = None
    if len(all_chambers) > 1:
        _info("Colonization chamber (Enter to use same as fruiting):")
        for ch in all_chambers: _info(f"  [{ch['id']}] {ch['name']} ({ch['chamber_type'] or 'no type'})")
        col_cid = input("Colonization chamber ID (Enter to skip): ").strip()
        if col_cid and col_cid.isdigit():
            col_ch = conn.execute("SELECT * FROM chambers WHERE id=?", (col_cid,)).fetchone()
            if col_ch: col_chamber_id = col_ch["id"]
    label   = _ask("Batch label","Batch-1")
    species = _ask("Species (required)")
    if not species: _err("Species required."); conn.close(); return
    strain  = _ask("Strain (optional)")
    print("\n-- Substrate --")
    dry_wt  = _ask("Dry substrate weight (g) — required for BE calculation")
    straw   = _ask("Straw %","0"); hwd = _ask("Hardwood %","0")
    bran    = _ask("Bran %","0"); gyp = _ask("Gypsum %","0"); coco = _ask("Coco coir %","0")
    print("\n-- Sterilization --")
    s_meth  = _ask(f"Method ({'/'.join(STERIL_METHODS)})","pressure_cooker")
    s_temp  = _ask("Temp F (optional)"); s_dur = _ask("Duration min (optional)")
    print("\n-- Spawn --")
    sp_type = _ask(f"Spawn type ({'/'.join(SPAWN_TYPES)})","grain")
    sp_str  = _ask("Spawn strain (optional)"); sp_rate = _ask("Spawn rate % (optional)")
    sp_src  = _ask("Source/supplier (optional)"); sp_lot = _ask("Lot # (optional)")
    print("\n-- Status --")
    inoc_dt = _ask("Inoculation date",str(date.today()))
    status  = _ask(f"Status ({'/'.join(STATUSES)})","colonizing")
    notes   = _ask("Notes (optional)")
    conn.execute("""INSERT INTO batches
        (chamber_id,colonization_chamber_id,label,species,strain,dry_weight_g,
         straw_pct,hardwood_pct,bran_pct,gypsum_pct,coco_pct,
         steril_method,steril_temp_f,steril_duration_min,
         inoculation_date,spawn_type,spawn_strain,spawn_rate_pct,spawn_source,spawn_lot,
         status,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (chamber["id"],col_chamber_id,label,species,strain or None,
         float(dry_wt) if dry_wt else None,
         float(straw),float(hwd),float(bran),float(gyp),float(coco),
         s_meth or None,float(s_temp) if s_temp else None,int(s_dur) if s_dur else None,
         inoc_dt,sp_type or None,sp_str or None,
         float(sp_rate) if sp_rate else None,sp_src or None,sp_lot or None,
         status,notes or None))
    conn.commit()
    bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    _ok(f"Batch '{label}' added (ID: {bid}).")


def cmd_batch_list(args):
    init_db(); conn = get_db()
    batches = conn.execute("SELECT * FROM batches ORDER BY id").fetchall()
    conn.close()
    if not batches: _info("No batches yet."); return
    _hdr("Batches")
    if RICH:
        t = Table(box=box.ROUNDED, header_style="bold cyan")
        for col in ["ID","Label","Species","Status","Days","Yield (g)","BE %"]: t.add_column(col)
        sc = {"colonizing":"yellow","colonized":"cyan","pinning":"blue","fruiting":"green",
              "resting":"white","done":"dim","contaminated":"red","aborted":"red"}
        for b in batches:
            be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
            col = sc.get(b["status"],"white")
            t.add_row(str(b["id"]),b["label"],b["species"],
                      f"[{col}]{b['status']}[/{col}]",
                      str(_days_since(b["inoculation_date"]) or "-"),
                      f"{b['total_yield_g']:.0f}",
                      f"{be:.0f}%" if be else "-")
        console.print(t)
    else:
        fmt = "{:<4} {:<12} {:<18} {:<13} {:<6} {:<10} {}"
        print(fmt.format("ID","Label","Species","Status","Days","Yield(g)","BE%"))
        print("-"*72)
        for b in batches:
            be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
            print(fmt.format(b["id"],b["label"],b["species"],b["status"],
                             _days_since(b["inoculation_date"]) or "-",
                             f"{b['total_yield_g']:.0f}",f"{be:.0f}%" if be else "-"))


def cmd_batch_update(args):
    init_db(); conn = get_db()
    b = conn.execute("SELECT * FROM batches WHERE id=?",(args.id,)).fetchone()
    if not b: _err(f"Batch {args.id} not found."); conn.close(); return
    _hdr(f"Update: {b['label']} ({b['species']})")
    status = _ask(f"New status ({'/'.join(STATUSES)})",b["status"])
    updates = {"status":status}; today = str(date.today())
    if status == "colonized" and not b["colonization_end_date"]:
        updates["colonization_end_date"] = _ask("Colonization end date",today)
    if status == "pinning" and not b["first_pin_date"]:
        updates["first_pin_date"] = _ask("First pin date",today)
    if status == "contaminated":
        updates["contamination_flag"] = 1
        updates["contamination_type"] = _ask("Type (trich/wet_rot/bacterial/other)")
    if status == "done" and not b["block_end_date"]:
        updates["block_end_date"] = _ask("Block end date", today)
    if status == "aborted":
        updates["abort_flag"] = 1; updates["abort_date"] = _ask("Abort date",today)
    notes = _ask("Notes (optional)")
    if notes: updates["notes"] = notes
    sql = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE batches SET {sql} WHERE id=?",(*updates.values(),args.id))
    conn.commit(); conn.close()
    _ok(f"Batch {args.id} -> '{status}'.")


def cmd_flush_log(args):
    init_db(); conn = get_db()
    b = conn.execute("SELECT * FROM batches WHERE id=?",(args.batch_id,)).fetchone()
    if not b: _err(f"Batch {args.batch_id} not found."); conn.close(); return
    _hdr(f"Log Flush - {b['label']} ({b['species']})")
    be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
    if be: _info(f"Current BE: {be}%  Yield: {b['total_yield_g']:.0f}g")
    flush_num  = int(_ask("Flush number",str(b["total_flushes"]+1)))
    pinning_dt = _ask("Pinning date (optional)")
    harvest_dt = _ask("Harvest date",str(date.today()))
    weight     = _ask("Fresh weight (g)")
    if not weight: _err("Weight required."); conn.close(); return
    quality    = _ask("Quality 1-5 (optional)")
    notes      = _ask("Notes (optional)")
    w = float(weight)
    conn.execute("INSERT INTO flushes(batch_id,flush_number,pinning_date,harvest_date,fresh_weight_g,quality_rating,notes) VALUES(?,?,?,?,?,?,?)",
                 (args.batch_id,flush_num,pinning_dt or None,harvest_dt,w,int(quality) if quality else None,notes or None))
    conn.execute("UPDATE batches SET total_flushes=?,total_yield_g=total_yield_g+?,status='resting' WHERE id=?",
                 (flush_num,w,args.batch_id))
    conn.commit()
    new_be = bio_efficiency(b["total_yield_g"]+w,b["dry_weight_g"])
    conn.close()
    _ok(f"Flush #{flush_num}: {w:.0f}g" + (f"  New BE: {new_be}%" if new_be else ""))


def cmd_flush_list(args):
    init_db(); conn = get_db()
    bid = getattr(args,"batch_id",None)
    q = ("SELECT f.*,b.label,b.species FROM flushes f JOIN batches b ON f.batch_id=b.id WHERE f.batch_id=? ORDER BY f.flush_number"
         if bid else
         "SELECT f.*,b.label,b.species FROM flushes f JOIN batches b ON f.batch_id=b.id ORDER BY f.created_at DESC LIMIT 40")
    rows = conn.execute(q,(bid,) if bid else ()).fetchall()
    conn.close()
    if not rows: _info("No flushes yet."); return
    _hdr("Flush Log")
    if RICH:
        t = Table(box=box.SIMPLE, header_style="bold cyan")
        for col in ["Date","Batch","Species","Flush","Weight(g)","Quality","Notes"]: t.add_column(col)
        for r in rows:
            q_str = f"[green]{'*'*r['quality_rating']}[/green]" if r["quality_rating"] else "-"
            t.add_row((r["harvest_date"] or "")[:10],r["label"],r["species"],
                      f"#{r['flush_number']}",f"{r['fresh_weight_g']:.0f}",q_str,r["notes"] or "")
        console.print(t)
    else:
        fmt = "{:<12} {:<12} {:<16} {:<7} {:<10} {:<8} {}"
        print(fmt.format("Date","Batch","Species","Flush","Weight(g)","Quality","Notes"))
        print("-"*72)
        for r in rows:
            print(fmt.format((r["harvest_date"] or "")[:10],r["label"],r["species"],
                             f"#{r['flush_number']}",f"{r['fresh_weight_g']:.0f}",
                             str(r["quality_rating"]) if r["quality_rating"] else "-",r["notes"] or ""))


def cmd_env_log(args):
    init_db(); conn = get_db(); chamber = _primary_chamber(conn)
    _hdr(f"Log Environment - {chamber['name']}")
    active_batch = conn.execute(
        "SELECT * FROM batches WHERE chamber_id=? AND status NOT IN ('retired','aborted','contaminated') ORDER BY id DESC LIMIT 1",
        (chamber["id"],)).fetchone()
    if active_batch:
        _info(f"Active batch: {active_batch['label']} ({active_batch['species']}) — Targets: {active_batch['target_temp_f']}F | {active_batch['target_humidity_rh']}% RH")
        target_temp = active_batch["target_temp_f"]
    else:
        _info(f"Chamber defaults — Targets: {chamber['target_temp_f']}F | {chamber['target_humidity_rh']}% RH")
        target_temp = chamber["target_temp_f"]
    phase    = _ask("Phase (colonization/fruiting/ambient)","fruiting")
    temp     = _ask("Temperature F")
    humidity = _ask("Humidity % RH")
    if not temp or not humidity: _err("Temp and humidity required."); conn.close(); return
    co2      = _ask("CO2 ppm (optional)")
    fae      = _ask("FAE fan cycles/day (optional)")
    light    = _ask("Light hours (optional)")
    misting  = _ask("Misting count (optional)")
    notes    = _ask("Notes (optional)")
    conn.execute("INSERT INTO environment_logs(chamber_id,phase,temp_f,humidity_rh,co2_ppm,fae_fan_cycles_day,light_hours,misting_count,notes) VALUES(?,?,?,?,?,?,?,?,?)",
                 (chamber["id"],phase,float(temp),float(humidity),
                  float(co2) if co2 else None,int(fae) if fae else None,
                  float(light) if light else None,int(misting) if misting else None,notes or None))
    conn.commit(); conn.close()
    temp_ok = abs(float(temp)-target_temp) <= 3
    hum_ok  = float(humidity) >= 80
    _ok(f"Logged {float(temp):.1f}F / {float(humidity):.0f}% RH"
        +(" [CHECK TEMP]" if not temp_ok else "")+(" [HUM LOW]" if not hum_ok else ""))


def cmd_env_history(args):
    init_db(); conn = get_db(); chamber = _primary_chamber(conn)
    limit = getattr(args,"limit",20) or 20
    logs = conn.execute("SELECT * FROM environment_logs WHERE chamber_id=? ORDER BY logged_at DESC LIMIT ?",
                        (chamber["id"],limit)).fetchall()
    conn.close()
    if not logs: _info("No env logs yet."); return
    _hdr(f"Environment History - {chamber['name']} (last {limit})")
    if RICH:
        t = Table(box=box.SIMPLE, header_style="bold cyan")
        for col in ["Timestamp","Phase","Temp F","Hum %","CO2","FAE","Light h","Notes"]: t.add_column(col)
        for l in logs:
            t.add_row(l["logged_at"][:16],l["phase"] or "-",
                      str(l["temp_f"]) if l["temp_f"] else "-",
                      str(l["humidity_rh"]) if l["humidity_rh"] else "-",
                      str(l["co2_ppm"]) if l["co2_ppm"] else "-",
                      str(l["fae_fan_cycles_day"]) if l["fae_fan_cycles_day"] else "-",
                      str(l["light_hours"]) if l["light_hours"] else "-",
                      l["notes"] or "")
        console.print(t)
    else:
        fmt = "{:<18} {:<12} {:<8} {:<7} {:<6} {:<5} {:<8} {}"
        print(fmt.format("Timestamp","Phase","Temp F","Hum %","CO2","FAE","Light h","Notes"))
        print("-"*78)
        for l in logs:
            print(fmt.format(l["logged_at"][:16],l["phase"] or "-",
                             l["temp_f"] or "-",l["humidity_rh"] or "-",
                             l["co2_ppm"] or "-",l["fae_fan_cycles_day"] or "-",
                             l["light_hours"] or "-",l["notes"] or ""))


def cmd_status(args):
    init_db(); conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers").fetchall()
    if not chambers: _err("No setup. Run: python mushroom_tracker.py setup"); conn.close(); return
    for ch in chambers:
        _hdr(f"Dashboard - {ch['name']} ({ch['location']})")
        latest = conn.execute("SELECT * FROM environment_logs WHERE chamber_id=? ORDER BY logged_at DESC LIMIT 1",(ch["id"],)).fetchone()
        if latest:
            _info(f"Last env ({_time_ago(latest['logged_at'])}): {latest['temp_f']}F  {latest['humidity_rh']}% RH  phase={latest['phase'] or '?'}")
        batches = conn.execute("SELECT * FROM batches WHERE chamber_id=? ORDER BY id",(ch["id"],)).fetchall()
        _info(f"\nBatches ({len(batches)}):")
        for b in batches:
            be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
            days = _days_since(b["inoculation_date"])
            _info(f"  [{b['id']}] {b['label']} - {b['species']} | {b['status']}"
                  +(f" | Day {days}" if days else "")
                  +f" | {b['total_flushes']} flush(es) {b['total_yield_g']:.0f}g"
                  +(f" | BE: {be}%" if be else ""))
    conn.close()


def cmd_report(args):
    init_db(); conn = get_db()
    batches = conn.execute("SELECT * FROM batches").fetchall()
    if not batches: _info("No batches yet."); conn.close(); return
    _hdr("Performance Report")
    total_yield = sum(b["total_yield_g"] for b in batches)
    active = sum(1 for b in batches if b["status"] not in ("done","contaminated","aborted"))
    _info(f"Batches: {len(batches)} total | {active} active | Yield: {total_yield:.0f}g")
    sorted_b = sorted(batches, key=lambda b: (bio_efficiency(b["total_yield_g"],b["dry_weight_g"]) or -1), reverse=True)
    if RICH:
        t = Table(title="BE Ranking", box=box.ROUNDED, header_style="bold cyan")
        for col in ["Label","Species","Dry Wt(g)","Yield(g)","BE %","Status"]: t.add_column(col)
        for b in sorted_b:
            be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
            col = "green" if (be or 0)>=60 else ("yellow" if (be or 0)>=30 else "red")
            t.add_row(b["label"],b["species"],
                      f"{b['dry_weight_g']:.0f}" if b["dry_weight_g"] else "-",
                      f"{b['total_yield_g']:.0f}",
                      f"[{col}]{be:.0f}%[/{col}]" if be else "-",
                      b["status"])
        console.print(t)
    else:
        fmt = "{:<12} {:<18} {:<10} {:<10} {:<8} {}"
        print(fmt.format("Label","Species","DryWt(g)","Yield(g)","BE%","Status"))
        print("-"*68)
        for b in sorted_b:
            be = bio_efficiency(b["total_yield_g"],b["dry_weight_g"])
            print(fmt.format(b["label"],b["species"],
                             f"{b['dry_weight_g']:.0f}" if b["dry_weight_g"] else "-",
                             f"{b['total_yield_g']:.0f}",
                             f"{be:.0f}%" if be else "-",b["status"]))
    conn.close()


# ── Entry ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Mushroom Tracker CLI v2")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("setup"); sub.add_parser("status"); sub.add_parser("report")
    bp = sub.add_parser("batch"); bs = bp.add_subparsers(dest="subcommand")
    bs.add_parser("add"); bs.add_parser("list")
    u = bs.add_parser("update"); u.add_argument("id",type=int)
    fp = sub.add_parser("flush"); fs = fp.add_subparsers(dest="subcommand")
    fl = fs.add_parser("log"); fl.add_argument("batch_id",type=int)
    fls = fs.add_parser("list"); fls.add_argument("batch_id",type=int,nargs="?")
    ep = sub.add_parser("env"); es = ep.add_subparsers(dest="subcommand")
    es.add_parser("log")
    eh = es.add_parser("history"); eh.add_argument("--limit",type=int,default=20)
    # Legacy aliases
    blk = sub.add_parser("block"); blks = blk.add_subparsers(dest="subcommand")
    blks.add_parser("add"); blks.add_parser("list")
    bu = blks.add_parser("update"); bu.add_argument("id",type=int)
    hp = sub.add_parser("harvest"); hs = hp.add_subparsers(dest="subcommand")
    hl = hs.add_parser("log"); hl.add_argument("block_id",type=int)

    args = p.parse_args()
    cmd = args.command; sub_ = getattr(args,"subcommand",None)
    if cmd == "block": cmd = "batch"
    if cmd == "harvest":
        cmd = "flush"; sub_ = "log"
        if hasattr(args,"block_id"): args.batch_id = args.block_id

    dispatch = {
        ("setup",None):cmd_setup, ("status",None):cmd_status, ("report",None):cmd_report,
        ("batch","add"):cmd_batch_add, ("batch","list"):cmd_batch_list, ("batch","update"):cmd_batch_update,
        ("flush","log"):cmd_flush_log, ("flush","list"):cmd_flush_list,
        ("env","log"):cmd_env_log, ("env","history"):cmd_env_history,
    }
    fn = dispatch.get((cmd,sub_))
    if fn: fn(args)
    else: p.print_help()


if __name__ == "__main__":
    main()
