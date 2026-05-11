#!/usr/bin/env python3
"""
seed_data.py — Populate mushroom_data.db with 6 months (Jan–June 2026)
of realistic test data.  Run from c:\\Python Scripts: python seed_data.py

Scope: 20 batches (8 BO / 5 LM / 4 SK / 3 KO), flushes, env logs at 4x/day,
Saturday farmer's market sales.  Wipes existing batch/flush/env/sales data;
preserves the existing chamber record.
"""

import sqlite3
import random
import sys
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
_SANDBOX = "--sandbox" in sys.argv
DB_PATH = Path(__file__).parent / ("mushroom_data_sandbox.db" if _SANDBOX else "mushroom_data.db")
LB_TO_G = 453.592

# ── Species parameters ─────────────────────────────────────────────────────────

SP = {
    "Blue Oyster": dict(
        col=(14, 18), pin=(3, 5),  harv=(4, 6),  rest=(7,  10), deg=0.48,
        ftmp=(67, 72), fhum=(90, 95), co2=(800, 1100), fae=(4, 6), mist=(2, 3),
        qual=4, fprice=14.0, dprice=65.0),
    "Lion's Mane": dict(
        col=(18, 24), pin=(5, 7),  harv=(5, 7),  rest=(10, 14), deg=0.42,
        ftmp=(65, 70), fhum=(90, 95), co2=(850, 1150), fae=(4, 6), mist=(2, 3),
        qual=4, fprice=20.0, dprice=None),
    "Shiitake": dict(
        col=(30, 45), pin=(7, 10), harv=(5, 8),  rest=(14, 21), deg=0.40,
        ftmp=(62, 68), fhum=(85, 92), co2=(900, 1200), fae=(3, 5), mist=(2, 3),
        qual=4, fprice=12.0, dprice=55.0),
    "King Oyster": dict(
        col=(20, 28), pin=(5, 8),  harv=(6, 9),  rest=(10, 14), deg=0.45,
        ftmp=(60, 68), fhum=(85, 92), co2=(800, 1100), fae=(4, 6), mist=(2, 3),
        qual=4, fprice=16.0, dprice=None),
}

# ── Substrate recipes ──────────────────────────────────────────────────────────

REC = {
    # hw=hardwood%, st=straw%, br=bran%, gy=gypsum%, co=coco%
    "hw":    dict(hw=80, st=0,  br=15, gy=5, co=0, other=None,
                  smethod="pressure_cooker", stemp=250, sdur=150),
    "straw": dict(hw=0,  st=90, br=10, gy=0, co=0, other=None,
                  smethod="pasteurization",  stemp=160, sdur=90),
    "lm":    dict(hw=85, st=0,  br=10, gy=5, co=0, other="oat bran 10%",
                  smethod="pressure_cooker", stemp=250, sdur=150),
    "sk":    dict(hw=90, st=0,  br=8,  gy=2, co=0, other=None,
                  smethod="pressure_cooker", stemp=250, sdur=150),
    "ko":    dict(hw=75, st=0,  br=20, gy=5, co=0, other=None,
                  smethod="pressure_cooker", stemp=250, sdur=150),
}

# ── Batch definitions ──────────────────────────────────────────────────────────
# n = number of productive flushes (0 = contaminated or aborted)
# be = biological efficiency target % (ignored when n=0)

BATCHES = [
    # ── Blue Oyster (8) ──────────────────────────────────────────────────────
    dict(label="BO-01", species="Blue Oyster",  inoc="2026-01-05", rec="hw",
         dw=2.2, be=95,  n=3, sup="North Spore",    lot="NS-2601-A", strain="POHU"),
    dict(label="BO-02", species="Blue Oyster",  inoc="2026-01-12", rec="straw",
         dw=2.0, be=85,  n=3, sup="Fungi Perfecti", lot="FP-2601-B", strain="WC"),
    dict(label="BO-03", species="Blue Oyster",  inoc="2026-01-19", rec="hw",
         dw=2.3, be=108, n=3, sup="North Spore",    lot="NS-2601-C", strain="POHU"),
    dict(label="BO-04", species="Blue Oyster",  inoc="2026-01-26", rec="hw",
         dw=2.1, be=0,   n=0, sup="Fungi Perfecti", lot="FP-2601-D", strain="WC",
         contam=True, ctype="trichoderma"),
    dict(label="BO-05", species="Blue Oyster",  inoc="2026-02-09", rec="straw",
         dw=2.4, be=88,  n=3, sup="North Spore",    lot="NS-2602-A", strain="POHU"),
    dict(label="BO-06", species="Blue Oyster",  inoc="2026-02-23", rec="hw",
         dw=2.2, be=102, n=3, sup="Fungi Perfecti", lot="FP-2602-B", strain="WC"),
    dict(label="BO-07", species="Blue Oyster",  inoc="2026-03-09", rec="hw",
         dw=2.5, be=90,  n=2, sup="North Spore",    lot="NS-2603-A", strain="POHU"),
    dict(label="BO-08", species="Blue Oyster",  inoc="2026-03-23", rec="straw",
         dw=2.0, be=82,  n=2, sup="Fungi Perfecti", lot="FP-2603-B", strain="WC"),

    # ── Lion's Mane (5) ─────────────────────────────────────────────────────
    dict(label="LM-01", species="Lion's Mane",  inoc="2026-01-10", rec="lm",
         dw=2.3, be=72,  n=2, sup="North Spore",    lot="NS-2601-D", strain="CM"),
    dict(label="LM-02", species="Lion's Mane",  inoc="2026-02-02", rec="lm",
         dw=2.2, be=0,   n=0, sup="Fungi Perfecti", lot="FP-2602-C", strain="CM",
         contam=True, ctype="bacterial_blotch"),
    dict(label="LM-03", species="Lion's Mane",  inoc="2026-02-16", rec="lm",
         dw=2.4, be=78,  n=2, sup="North Spore",    lot="NS-2602-B", strain="CM"),
    dict(label="LM-04", species="Lion's Mane",  inoc="2026-03-02", rec="lm",
         dw=2.1, be=0,   n=0, sup="Fungi Perfecti", lot="FP-2603-C", strain="CM",
         aborted=True),
    dict(label="LM-05", species="Lion's Mane",  inoc="2026-03-23", rec="lm",
         dw=2.3, be=65,  n=2, sup="North Spore",    lot="NS-2603-B", strain="CM"),

    # ── Shiitake (4) ────────────────────────────────────────────────────────
    dict(label="SK-01", species="Shiitake",     inoc="2026-01-07", rec="sk",
         dw=2.2, be=62,  n=3, sup="Fungi Perfecti", lot="FP-2601-A", strain="WR46"),
    dict(label="SK-02", species="Shiitake",     inoc="2026-01-28", rec="sk",
         dw=2.4, be=0,   n=0, sup="North Spore",    lot="NS-2602-C", strain="D101",
         contam=True, ctype="trichoderma"),
    dict(label="SK-03", species="Shiitake",     inoc="2026-02-18", rec="sk",
         dw=2.3, be=58,  n=3, sup="Fungi Perfecti", lot="FP-2602-D", strain="WR46"),
    dict(label="SK-04", species="Shiitake",     inoc="2026-03-18", rec="sk",
         dw=2.5, be=68,  n=2, sup="North Spore",    lot="NS-2603-C", strain="D101"),

    # ── King Oyster (3) ─────────────────────────────────────────────────────
    dict(label="KO-01", species="King Oyster",  inoc="2026-01-14", rec="ko",
         dw=2.3, be=82,  n=3, sup="Fungi Perfecti", lot="FP-2601-C", strain="PE6"),
    dict(label="KO-02", species="King Oyster",  inoc="2026-02-04", rec="ko",
         dw=2.1, be=88,  n=3, sup="North Spore",    lot="NS-2602-D", strain="PE5"),
    dict(label="KO-03", species="King Oyster",  inoc="2026-03-04", rec="ko",
         dw=2.4, be=75,  n=2, sup="Fungi Perfecti", lot="FP-2603-A", strain="PE6"),
]

# Anomaly events (chamber-wide)
HUM_ANOMALY_DATE  = date(2026, 2, 15)  # humidifier fault — 98%+ for two readings
TEMP_ANOMALY_DATE = date(2026, 3, 22)  # heater failure — 58°F for two readings


# ── Helpers ────────────────────────────────────────────────────────────────────

def next_saturday(d):
    """First Saturday on or after date d."""
    days = (5 - d.weekday()) % 7
    return d + timedelta(days=days)


def flush_yields(dw_g, be_pct, n_flushes, degradation):
    """Flush weights (g) summing to ≈ be_pct% of dw_g, degrading each flush."""
    target = dw_g * be_pct / 100.0
    weights = [(1.0 - degradation) ** i for i in range(n_flushes)]
    f1 = target / sum(weights)
    return [f1 * w * random.uniform(0.95, 1.05) for w in weights]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── Get or create chamber ──────────────────────────────────────────────────
    row = cur.execute("SELECT id FROM chambers LIMIT 1").fetchone()
    if row:
        ch_id = row["id"]
        print(f"Using existing chamber id={ch_id}.")
    else:
        cur.execute(
            "INSERT INTO chambers (name, location, target_temp_f, target_humidity_rh)"
            " VALUES (?,?,?,?)",
            ("Main Fruiting Chamber", "Basement", 70.0, 90.0))
        ch_id = cur.lastrowid
        conn.commit()
        print(f"Created chamber id={ch_id}.")

    # ── Wipe operational tables (preserve chambers) ────────────────────────────
    for tbl in ("sales", "environment_logs", "flushes", "batches"):
        cur.execute(f"DELETE FROM {tbl}")
    conn.commit()
    print("Cleared existing batches / flushes / env logs / sales.\n")

    # ── Batches + Flushes ──────────────────────────────────────────────────────
    harvests = []  # dicts fed to the sales generator

    for bd in BATCHES:
        sp  = SP[bd["species"]]
        rec = REC[bd["rec"]]
        inoc  = date.fromisoformat(bd["inoc"])
        dw_g  = bd["dw"] * LB_TO_G
        moist = round(random.uniform(58.0, 63.0), 1)
        srate = round(random.uniform(15.0, 20.0), 1)

        is_contam = bd.get("contam",   False)
        is_abort  = bd.get("aborted",  False)
        ctype     = bd.get("ctype",    None)
        n_flush   = bd["n"]

        # Colonization end date
        if is_contam:
            col_end = inoc + timedelta(days=random.randint(8, 14))
            status  = "contaminated"
        else:
            col_end = inoc + timedelta(days=random.randint(*sp["col"]))
            status  = "aborted" if is_abort else "done"

        # Aborted blocks pinned briefly before being discarded
        abort_pin = None
        if is_abort:
            abort_pin = col_end + timedelta(days=random.randint(*sp["pin"]))

        cur.execute("""
            INSERT INTO batches (
                chamber_id, label, species, strain,
                dry_weight_g, moisture_pct,
                hardwood_pct, straw_pct, bran_pct, gypsum_pct, coco_pct,
                substrate_other,
                steril_method, steril_temp_f, steril_duration_min,
                inoculation_date, colonization_start_date, colonization_end_date,
                spawn_type, spawn_strain, spawn_rate_pct, spawn_source, spawn_lot,
                first_pin_date, status,
                contamination_flag, contamination_type,
                abort_flag,
                total_flushes, total_yield_g
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ch_id, bd["label"], bd["species"], bd["strain"],
            round(dw_g, 1), moist,
            rec["hw"], rec["st"], rec["br"], rec["gy"], rec["co"], rec["other"],
            rec["smethod"], rec["stemp"], rec["sdur"],
            inoc.isoformat(), inoc.isoformat(), col_end.isoformat(),
            "grain", bd["strain"], srate, bd["sup"], bd["lot"],
            abort_pin.isoformat() if abort_pin else None,
            status,
            int(is_contam), ctype,
            int(is_abort),
            0, 0.0,
        ))
        batch_id = cur.lastrowid

        if n_flush == 0:
            print(f"  {bd['label']:6s}  {bd['species']:15s}  {status}")
            continue

        # ── Generate flush schedule ────────────────────────────────────────────
        yields   = flush_yields(dw_g, bd["be"], n_flush, sp["deg"])
        cur_date = col_end
        fp_date  = None
        total_y  = 0.0
        flush_notes = {
            1: "Good cluster formation, healthy pins.",
            2: "Slightly smaller clusters on second flush.",
            3: "Substrate tiring; smaller yield expected.",
        }

        for fi, weight in enumerate(yields, 1):
            pin_date     = cur_date + timedelta(days=random.randint(*sp["pin"]))
            harvest_date = pin_date  + timedelta(days=random.randint(*sp["harv"]))

            if fi == 1:
                fp_date = pin_date
                qual = min(5, sp["qual"] + random.choice([0, 0, 1]))
            elif fi == n_flush:
                qual = max(2, sp["qual"] - random.choice([1, 2]))
            else:
                qual = sp["qual"]

            cur.execute("""
                INSERT INTO flushes (batch_id, flush_number, pinning_date,
                                     harvest_date, fresh_weight_g, quality_rating, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (batch_id, fi, pin_date.isoformat(), harvest_date.isoformat(),
                  round(weight, 1), qual, flush_notes.get(fi)))
            flush_id = cur.lastrowid

            harvests.append(dict(
                batch_id=batch_id, flush_id=flush_id,
                harvest_date=harvest_date,
                species=bd["species"], weight_g=weight,
            ))
            total_y  += weight
            cur_date  = harvest_date + timedelta(days=random.randint(*sp["rest"]))

        cur.execute(
            "UPDATE batches SET total_flushes=?, total_yield_g=?, first_pin_date=?"
            " WHERE id=?",
            (n_flush, round(total_y, 1),
             fp_date.isoformat() if fp_date else None, batch_id))

        be_actual = round(total_y / dw_g * 100, 1)
        print(f"  {bd['label']:6s}  {bd['species']:15s}  {n_flush} flushes  "
              f"{round(total_y):4d}g  BE {be_actual}%")

    conn.commit()
    print(f"\nInserted {len(BATCHES)} batches.")

    # ── Environment logs ───────────────────────────────────────────────────────
    # Chamber-wide, 4x/day (00:00 / 06:00 / 12:00 / 18:00), Jan 5 – Jun 30.
    # Diurnal pattern: warmest/driest at noon, coolest/most humid at midnight.
    # Two anomaly events embedded.

    env_rows = []
    d = date(2026, 1, 5)
    while d <= date(2026, 6, 30):
        for hr in (0, 6, 12, 18):
            note = None

            # Diurnal temperature and humidity deltas
            if hr == 0:      # midnight — coolest, most humid
                td = random.uniform(-1.5, -0.5)
                hd = random.uniform( 0.5,  1.5)
            elif hr == 6:    # dawn — still cool
                td = random.uniform(-0.5,  0.5)
                hd = random.uniform( 0.0,  1.0)
            elif hr == 12:   # noon — warmest, afternoon humidity drop
                td = random.uniform( 0.5,  2.0)
                hd = random.uniform(-4.0, -2.0)
            else:            # 18:00 — cooling, humidity recovering
                td = random.uniform( 0.0,  1.0)
                hd = random.uniform(-1.5,  0.0)

            temp = round(70.0 + td + random.uniform(-0.3, 0.3), 1)
            hum  = round(92.0 + hd + random.uniform(-0.5, 0.5), 1)
            hum  = max(75.0, min(97.0, hum))
            co2  = int(random.uniform(850, 1100))
            fae  = random.randint(4, 6)
            mist = random.randint(2, 3)

            # Anomaly: humidifier fault — Feb 15 noon and 18:00
            if d == HUM_ANOMALY_DATE and hr in (12, 18):
                hum = round(random.uniform(97.5, 98.5), 1)
                if hr == 12:
                    note = "Humidifier controller fault — spike to 98%+. Adjusted at 18:00."

            # Anomaly: heater failure — Mar 22 midnight and 06:00
            if d == TEMP_ANOMALY_DATE and hr in (0, 6):
                temp = round(random.uniform(57.5, 59.0), 1)
                if hr == 0:
                    note = "Heater failure overnight — temp dropped to ~58F. Resolved by 06:00."

            phase = "colonization" if d < date(2026, 1, 22) else "fruiting"

            env_rows.append((
                ch_id, None,
                f"{d.isoformat()} {hr:02d}:00:00",
                phase, temp, hum, co2, fae, mist, note,
            ))
        d += timedelta(days=1)

    cur.executemany("""
        INSERT INTO environment_logs
            (chamber_id, batch_id, logged_at, phase,
             temp_f, humidity_rh, co2_ppm, fae_fan_cycles_day, misting_count, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, env_rows)
    conn.commit()
    print(f"Inserted {len(env_rows)} environment log entries "
          f"(anomalies: {HUM_ANOMALY_DATE} humidity, {TEMP_ANOMALY_DATE} temp).")

    # ── Sales ──────────────────────────────────────────────────────────────────
    # Each harvest sold at next Saturday farmer's market.
    # Blue oyster + shiitake: 70% fresh / 30% dried (two sale rows per harvest).
    # Lion's mane + king oyster: 100% fresh (one sale row per harvest).

    sale_rows = []
    for h in harvests:
        sp     = SP[h["species"]]
        sale_d = next_saturday(h["harvest_date"] + timedelta(days=1))
        if sale_d > date(2026, 6, 30):
            continue

        wg = h["weight_g"]
        if sp["dprice"] is not None:
            # Fresh sale (70%)
            sale_rows.append((
                h["batch_id"], h["flush_id"], sale_d.isoformat(),
                round(wg * 0.70, 1), None,
                sp["fprice"], "farmers_market", None,
            ))
            # Dried sale (30% of fresh weight → 10:1 conversion)
            sale_rows.append((
                h["batch_id"], h["flush_id"], sale_d.isoformat(),
                None, round(wg * 0.30 / 10.0, 1),
                sp["dprice"], "farmers_market", "dried",
            ))
        else:
            # All fresh
            sale_rows.append((
                h["batch_id"], h["flush_id"], sale_d.isoformat(),
                round(wg, 1), None,
                sp["fprice"], "farmers_market", None,
            ))

    cur.executemany("""
        INSERT INTO sales
            (batch_id, flush_id, sale_date,
             fresh_weight_sold_g, dried_weight_sold_g,
             price_per_lb, destination, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, sale_rows)
    conn.commit()
    print(f"Inserted {len(sale_rows)} sale records.")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n--- Results by species -------------------------------------------")
    for row in cur.execute("""
        SELECT species,
               COUNT(*)                                                   total,
               SUM(contamination_flag)                                    contam,
               SUM(abort_flag)                                            aborts,
               SUM(total_flushes)                                         flushes,
               ROUND(SUM(total_yield_g) / 1000.0, 2)                     kg,
               ROUND(AVG(CASE WHEN total_yield_g > 0 AND dry_weight_g > 0
                          THEN total_yield_g / dry_weight_g * 100 END), 1) avg_be
        FROM batches
        GROUP BY species
        ORDER BY species
    """):
        print(f"  {row[0]:15s}  {row[1]} batches "
              f"({int(row[2] or 0)} contam / {int(row[3] or 0)} abort)  "
              f"{int(row[4] or 0)} flushes  {row[5] or 0} kg  "
              f"avg BE {row[6] or '—'}%")

    rev = cur.execute("""
        SELECT ROUND(SUM(
            COALESCE(fresh_weight_sold_g, dried_weight_sold_g) / 453.592 * price_per_lb
        ), 2)
        FROM sales
    """).fetchone()[0]
    flush_count = cur.execute("SELECT COUNT(*) FROM flushes").fetchone()[0]
    print(f"\n  Total flushes logged : {flush_count}")
    print(f"  Total sale rows      : {len(sale_rows)}")
    print(f"  Estimated revenue    : ${rev:,.2f}" if rev else "  No revenue data.")
    print(f"  Env log entries      : {len(env_rows)}")
    print("\nDone. Refresh the app in your browser.")
    conn.close()


if __name__ == "__main__":
    print(f"Target DB: {DB_PATH}  ({'SANDBOX' if _SANDBOX else 'PRODUCTION'})")
    main()
