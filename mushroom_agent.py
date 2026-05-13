"""
Mushroom Tracker AI Monitoring Agent

Queries the database, calls Claude, and writes a daily briefing.

Run standalone:   python mushroom_agent.py
Web trigger:      POST /briefing/run  (via mushroom_app.py)
Scheduled:        daily at 06:00 via APScheduler (started in mushroom_app.py)
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

import mushroom_tracker as _mt
from agent_config import (
    DEFAULT_TIMELINE, ENV_GUARDRAILS, FLUSH_DEGRADATION,
    MIN_HISTORY_BATCHES, SPECIES_TIMELINES,
)

SYSTEM_PROMPT = """\
You are a mushroom cultivation monitoring agent. You analyze batch status data \
and environmental conditions against defined species timelines and goals, then \
generate a concise prioritized daily briefing for the grower.

Your evaluation criteria are provided in the data snapshot under \
'goals_and_thresholds'. Always reason against the grower's own historical \
averages when available; fall back to species targets when history is thin \
(fewer than 5 completed batches for that species).

IMPORTANT — sourced blocks: if a batch has "sourced_block": true, it is a \
commercially prepared fruiting block purchased from a supplier (e.g. North Spore). \
Do NOT flag missing dry_weight_g, substrate percentages, sterilization method, \
spawn type, or spawn lot — these fields are not applicable and their absence is \
expected. Focus monitoring for sourced blocks on lifecycle timing, environmental \
conditions, and flush performance only. \
For any batch (sourced or not), use the "in_chamber" field to determine whether \
the block is currently in the fruiting chamber (derived from fruiting_start_date). \
If in_chamber is true, apply fruiting environment standards even if status is still \
"colonized". If in_chamber is false and status is "colonized", the block is \
intentionally being held outside the chamber — either in cold shock or pre-chamber \
staging. This is NORMAL and EXPECTED grower workflow. Do NOT flag it for missing \
fruiting-chamber readings, do NOT prompt the grower to confirm placement or update \
the record, and do NOT evaluate it against fruiting guardrails. The grower will \
set fruiting_start_date when the block enters the chamber. \
Additionally, if the batch has "sourced_block": true AND in_chamber is false, \
do NOT raise colonization-temperature concerns — the block is already commercially \
colonized, so colonization conditions are irrelevant. The only temperature planning \
that matters is whether the fruiting chamber will suit the species once the block \
is placed; evaluate that against fruiting temperature targets, not colonization ones.

GROWER NOTES — each active batch may include a "recent_notes" list of \
timestamped observations the grower logged directly (last 14 days, up to 10 \
entries). Treat these as ground truth about what the grower has already \
noticed or acted on. Before raising an issue, check whether the grower has \
already identified it or taken corrective action — if so, acknowledge the \
action rather than re-flagging the problem. Use notes as context for \
pattern observations (e.g. if the grower noted a manual humidity adjustment, \
that explains a dip in the sensor data). Never surface a note back to the \
grower verbatim — synthesize it into your analysis.

Output format — return JSON only, no preamble:
{
  "briefing_date": "YYYY-MM-DD",
  "attention_required": [
    {
      "batch_id": int,
      "batch_label": "str",
      "species": "str",
      "issue": "str",
      "severity": "critical|warning|info",
      "suggested_action": "str"
    }
  ],
  "on_track": [
    {"batch_id": int, "batch_label": "str", "species": "str"}
  ],
  "environmental_alerts": [
    {
      "batch_id": int,
      "parameter": "str",
      "observed": "str",
      "expected_range": "str",
      "duration_hours": "str"
    }
  ],
  "pattern_observations": ["str"],
  "summary": "str"
}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_between(d1_str, d2_str=None):
    if not d1_str:
        return None
    try:
        d1 = datetime.strptime(str(d1_str)[:10], "%Y-%m-%d").date()
        d2 = (datetime.strptime(str(d2_str)[:10], "%Y-%m-%d").date()
              if d2_str else date.today())
        return (d2 - d1).days
    except Exception:
        return None


def _batch_guardrails(status: str, species_key: str, in_chamber: bool = False):
    """
    Return (temp_range, hum_range, co2_range, min_hours) for one batch.
    Uses the batch's actual lifecycle status and overlays species-specific targets.
    If in_chamber=True (fruiting_start_date is set) and status is still colonized,
    fruiting guardrails are used — the block is in the chamber regardless of status label.
    """
    effective_status = status
    if in_chamber and status in ('colonizing', 'colonized'):
        effective_status = 'fruiting'

    phase_key  = effective_status if effective_status in ENV_GUARDRAILS else 'fruiting'
    base       = ENV_GUARDRAILS.get(phase_key, ENV_GUARDRAILS['fruiting'])

    temp_range = base.get('temp_f',      (60, 85))
    hum_range  = base.get('humidity_rh', (80, 95))
    co2_range  = base.get('co2_ppm')
    min_hours  = base.get('consecutive_hours_to_flag', 2)

    sp = SPECIES_TIMELINES.get(species_key or '', {})
    if effective_status in ('pinning', 'fruiting'):
        if 'fruiting_temp_f'      in sp: temp_range = sp['fruiting_temp_f']
        if 'fruiting_humidity_rh' in sp: hum_range  = sp['fruiting_humidity_rh']
    elif effective_status in ('colonizing', 'colonized'):
        if 'colonization_temp_f'  in sp: temp_range = sp['colonization_temp_f']

    return temp_range, hum_range, co2_range, min_hours


# ── Data collection ───────────────────────────────────────────────────────────

def _get_active_batches(conn) -> list:
    rows = conn.execute("""
        SELECT b.*, c.name AS chamber_name, c.chamber_type
        FROM batches b
        LEFT JOIN chambers c ON b.chamber_id = c.id
        WHERE b.status NOT IN ('done', 'contaminated', 'aborted')
        ORDER BY b.id
    """).fetchall()

    result = []
    for row in rows:
        b = dict(row)
        b['days_since_inoculation'] = _days_between(b.get('inoculation_date'))

        b['sourced_block'] = bool(b.get('sourced_block'))
        b['in_chamber']    = bool(b.get('fruiting_start_date'))

        status = b.get('status', '')
        if status == 'colonizing':
            b['days_in_status'] = _days_between(b.get('inoculation_date'))
        elif status == 'colonized':
            b['days_in_status'] = _days_between(b.get('colonization_end_date'))
        elif status in ('pinning', 'fruiting'):
            b['days_in_status'] = _days_between(b.get('pinning_started_at'))
        else:
            b['days_in_status'] = None

        result.append(b)
    return result


def _get_latest_flush_per_batch(conn, batch_ids: list) -> dict:
    if not batch_ids:
        return {}
    ph = ','.join('?' * len(batch_ids))
    rows = conn.execute(f"""
        SELECT f.*,
               b.dry_weight_g,
               CASE WHEN b.dry_weight_g > 0
                    THEN ROUND(f.fresh_weight_g / b.dry_weight_g * 100, 1)
                    ELSE NULL END AS be_pct_this_flush
        FROM flushes f
        JOIN batches b ON f.batch_id = b.id
        WHERE f.batch_id IN ({ph})
          AND f.flush_number = (
              SELECT MAX(f2.flush_number) FROM flushes f2
              WHERE f2.batch_id = f.batch_id
          )
        ORDER BY f.batch_id
    """, batch_ids).fetchall()
    return {row['batch_id']: dict(row) for row in rows}


def _get_all_flushes_per_batch(conn, batch_ids: list) -> dict:
    if not batch_ids:
        return {}
    ph = ','.join('?' * len(batch_ids))
    rows = conn.execute(f"""
        SELECT f.*, b.dry_weight_g
        FROM flushes f
        JOIN batches b ON f.batch_id = b.id
        WHERE f.batch_id IN ({ph})
        ORDER BY f.batch_id, f.flush_number
    """, batch_ids).fetchall()
    result = {}
    for row in rows:
        bid = row['batch_id']
        result.setdefault(bid, []).append(dict(row))
    return result


def _get_env_summary(conn, batch_info_map: dict):
    """
    batch_info_map: {batch_id: {'chamber_id': int, 'status': str, 'species': str}}

    Includes chamber-level rows (batch_id IS NULL) from sensor imports and
    attributes them to every active batch sharing that chamber.
    Flags use each batch's actual status and species-specific thresholds.
    """
    if not batch_info_map:
        return {}, []

    batch_ids   = list(batch_info_map.keys())
    chamber_ids = list({v['chamber_id'] for v in batch_info_map.values()
                        if v.get('chamber_id')})

    # chamber_id → [batch_id, ...] for attributing chamber-level rows
    chamber_to_batches: dict = {}
    for bid, info in batch_info_map.items():
        cid = info.get('chamber_id')
        if cid:
            chamber_to_batches.setdefault(cid, []).append(bid)

    ph_b = ','.join('?' * len(batch_ids))

    if chamber_ids:
        ph_c = ','.join('?' * len(chamber_ids))
        detail_rows = conn.execute(f"""
            SELECT batch_id, chamber_id, logged_at, temp_f, humidity_rh, co2_ppm
            FROM environment_logs
            WHERE (
                (batch_id IN ({ph_b}))
                OR (batch_id IS NULL AND chamber_id IN ({ph_c}))
            )
              AND logged_at >= datetime('now', '-24 hours')
            ORDER BY logged_at
        """, batch_ids + chamber_ids).fetchall()
    else:
        detail_rows = conn.execute(f"""
            SELECT batch_id, chamber_id, logged_at, temp_f, humidity_rh, co2_ppm
            FROM environment_logs
            WHERE batch_id IN ({ph_b})
              AND logged_at >= datetime('now', '-24 hours')
            ORDER BY logged_at
        """, batch_ids).fetchall()

    # Attribute each row to the appropriate batch_id(s)
    by_batch: dict = {}
    for row in detail_rows:
        d = dict(row)
        if d['batch_id'] is not None:
            by_batch.setdefault(d['batch_id'], []).append(d)
        else:
            for bid in chamber_to_batches.get(d['chamber_id'], []):
                by_batch.setdefault(bid, []).append(d)

    # Build per-batch summaries in Python
    summaries: dict = {}
    for bid, readings in by_batch.items():
        temps = [r['temp_f']      for r in readings if r['temp_f']      is not None]
        hums  = [r['humidity_rh'] for r in readings if r['humidity_rh'] is not None]
        co2s  = [r['co2_ppm']     for r in readings if r['co2_ppm']     is not None]
        summaries[bid] = {
            'batch_id':        bid,
            'reading_count':   len(readings),
            'avg_temp_f':      round(sum(temps) / len(temps), 1) if temps else None,
            'min_temp_f':      round(min(temps), 1)              if temps else None,
            'max_temp_f':      round(max(temps), 1)              if temps else None,
            'avg_humidity_rh': round(sum(hums)  / len(hums),  1) if hums  else None,
            'min_humidity_rh': round(min(hums),  1)              if hums  else None,
            'max_humidity_rh': round(max(hums),  1)              if hums  else None,
            'avg_co2_ppm':     round(sum(co2s)  / len(co2s),  0) if co2s  else None,
            'min_co2_ppm':     round(min(co2s),  0)              if co2s  else None,
            'max_co2_ppm':     round(max(co2s),  0)              if co2s  else None,
        }

    flags = []
    for batch_id, readings in by_batch.items():
        readings.sort(key=lambda r: r['logged_at'])

        info        = batch_info_map.get(batch_id, {})
        status      = info.get('status', 'fruiting')
        species_key = (info.get('species') or '').lower()
        in_chamber  = info.get('in_chamber', False)

        temp_range, hum_range, co2_range, min_hours = _batch_guardrails(
            status, species_key, in_chamber
        )

        param_ranges = {'temp_f': temp_range, 'humidity_rh': hum_range}
        if co2_range:
            param_ranges['co2_ppm'] = co2_range

        for param, (lo, hi) in param_ranges.items():
            streak_start_time = None
            streak_last_val   = None

            for reading in readings:
                val = reading.get(param)
                if val is None:
                    streak_start_time = None
                    continue
                out_of_range = val < lo or val > hi
                if out_of_range:
                    if streak_start_time is None:
                        streak_start_time = reading['logged_at']
                    streak_last_val = val
                else:
                    if streak_start_time is not None:
                        try:
                            t1 = datetime.strptime(streak_start_time[:19], "%Y-%m-%d %H:%M:%S")
                            t2 = datetime.strptime(reading['logged_at'][:19], "%Y-%m-%d %H:%M:%S")
                            hours = (t2 - t1).total_seconds() / 3600
                            if hours >= min_hours:
                                flags.append({
                                    'batch_id':       batch_id,
                                    'parameter':      param,
                                    'observed':       streak_last_val,
                                    'expected_range': f"{lo}–{hi}",
                                    'duration_hours': round(hours, 1),
                                })
                        except Exception:
                            pass
                    streak_start_time = None
                    streak_last_val   = None

            # streak extends to end of window
            if streak_start_time is not None:
                try:
                    t1 = datetime.strptime(streak_start_time[:19], "%Y-%m-%d %H:%M:%S")
                    hours = (datetime.now() - t1).total_seconds() / 3600
                    if hours >= min_hours:
                        flags.append({
                            'batch_id':       batch_id,
                            'parameter':      param,
                            'observed':       streak_last_val,
                            'expected_range': f"{lo}–{hi}",
                            'duration_hours': round(hours, 1),
                        })
                except Exception:
                    pass

    return summaries, flags


def _get_batch_notes(conn, batch_ids: list) -> dict:
    """Return up to 10 most recent notes per batch from the last 14 days."""
    if not batch_ids:
        return {}
    ph = ','.join('?' * len(batch_ids))
    rows = conn.execute(f"""
        SELECT batch_id, body, created_at
        FROM batch_notes
        WHERE batch_id IN ({ph})
          AND created_at >= datetime('now', '-14 days')
        ORDER BY batch_id, created_at DESC
    """, batch_ids).fetchall()
    result = {}
    for row in rows:
        bid = row['batch_id']
        entries = result.setdefault(bid, [])
        if len(entries) < 10:
            entries.append({'note': row['body'], 'at': row['created_at'][:16]})
    # Return in chronological order
    for bid in result:
        result[bid] = list(reversed(result[bid]))
    return result


def _get_contamination_summary(conn) -> list:
    rows = conn.execute("""
        SELECT id, label, species, spawn_lot, spawn_source,
               contamination_type, created_at
        FROM batches
        WHERE contamination_flag = 1
        ORDER BY created_at DESC
        LIMIT 20
    """).fetchall()
    return [dict(row) for row in rows]


def _get_historical_averages(conn) -> dict:
    rows = conn.execute("""
        SELECT species,
               COUNT(*) AS completed_batches,
               ROUND(AVG(CASE WHEN dry_weight_g > 0
                   THEN total_yield_g / dry_weight_g * 100 END), 1) AS avg_be_pct,
               ROUND(AVG(CASE WHEN colonization_end_date IS NOT NULL
                   THEN julianday(colonization_end_date) - julianday(inoculation_date)
                   END), 1) AS avg_colonization_days,
               ROUND(AVG(CASE WHEN block_end_date IS NOT NULL AND inoculation_date IS NOT NULL
                   THEN julianday(block_end_date) - julianday(inoculation_date)
                   END), 1) AS avg_total_cycle_days,
               ROUND(AVG(total_flushes), 1) AS avg_flushes
        FROM batches
        WHERE status = 'done'
        GROUP BY species
    """).fetchall()
    hist = {row['species']: dict(row) for row in rows}

    pin_rows = conn.execute("""
        SELECT b.species,
               ROUND(AVG(julianday(f.pinning_date) - julianday(b.inoculation_date)), 1)
                   AS avg_days_to_first_pin,
               ROUND(AVG(julianday(f.harvest_date) - julianday(f.pinning_date)), 1)
                   AS avg_days_to_harvest
        FROM batches b
        JOIN flushes f ON b.id = f.batch_id AND f.flush_number = 1
        WHERE f.pinning_date IS NOT NULL AND b.inoculation_date IS NOT NULL
          AND f.harvest_date IS NOT NULL
        GROUP BY b.species
    """).fetchall()
    for row in pin_rows:
        sp = row['species']
        d = dict(row)
        if sp in hist:
            hist[sp].update(d)
        else:
            hist[sp] = d

    return hist


def get_snapshot(conn) -> dict:
    active_batches = _get_active_batches(conn)
    batch_ids = [b['id'] for b in active_batches]

    batch_info_map = {
        b['id']: {
            'chamber_id':        b.get('chamber_id'),
            'status':            b.get('status', 'fruiting'),
            'species':           b.get('species', ''),
            'sourced_block':     bool(b.get('sourced_block')),
            'in_chamber':        bool(b.get('fruiting_start_date')),
        }
        for b in active_batches
    }

    latest_flushes  = _get_latest_flush_per_batch(conn, batch_ids)
    all_flushes     = _get_all_flushes_per_batch(conn, batch_ids)
    env_summaries, env_flags = _get_env_summary(conn, batch_info_map)
    contamination   = _get_contamination_summary(conn)
    historical      = _get_historical_averages(conn)
    batch_notes     = _get_batch_notes(conn, batch_ids)

    for b in active_batches:
        sp_key = b['species'].lower()
        timeline = SPECIES_TIMELINES.get(sp_key, DEFAULT_TIMELINE)
        b['latest_flush']    = latest_flushes.get(b['id'])
        b['all_flushes']     = all_flushes.get(b['id'], [])
        b['env_24h']         = env_summaries.get(b['id'])
        b['species_targets'] = timeline
        b['recent_notes']    = batch_notes.get(b['id'], [])
        b['use_historical']  = (
            historical.get(b['species'], {}).get('completed_batches', 0) >= MIN_HISTORY_BATCHES
        )

    return {
        'snapshot_date':         str(date.today()),
        'active_batches':        active_batches,
        'env_flags':             env_flags,
        'contamination_recent':  contamination,
        'historical_averages':   historical,
        'goals_and_thresholds': {
            'species_timelines':    SPECIES_TIMELINES,
            'default_timeline':     DEFAULT_TIMELINE,
            'env_guardrails':       ENV_GUARDRAILS,
            'flush_degradation':    FLUSH_DEGRADATION,
            'min_history_batches':  MIN_HISTORY_BATCHES,
        },
    }


# ── Claude API ────────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as reg:
            value, _ = winreg.QueryValueEx(reg, 'ANTHROPIC_API_KEY')
            return value
    except Exception:
        return None


def call_claude(snapshot: dict) -> dict:
    if not _ANTHROPIC_AVAILABLE:
        raise RuntimeError("anthropic package not installed — run: pip install anthropic")
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(snapshot, default=str)}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split('\n')
        raw = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    return json.loads(raw)


# ── Persistence ───────────────────────────────────────────────────────────────

def save_briefing(conn, briefing_date: str, result: dict,
                  triggered_by: str = 'scheduler'):
    raw_json       = json.dumps(result)
    attention_count = len(result.get('attention_required', []))
    critical_count  = sum(
        1 for i in result.get('attention_required', [])
        if i.get('severity') == 'critical'
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM daily_briefings WHERE briefing_date = ?", (briefing_date,))
    conn.execute("""
        INSERT INTO daily_briefings
            (briefing_date, raw_json, attention_count, critical_count,
             triggered_by, generated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (briefing_date, raw_json, attention_count, critical_count,
          triggered_by, generated_at))
    conn.commit()


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_briefing(triggered_by: str = 'scheduler') -> dict:
    conn = _mt.get_db()
    try:
        snapshot = get_snapshot(conn)
        result   = call_claude(snapshot)
        result.setdefault('briefing_date', str(date.today()))
        save_briefing(conn, result['briefing_date'], result, triggered_by)
        logger.info(
            "Briefing generated for %s — %d items (%d critical), triggered_by=%s",
            result['briefing_date'],
            len(result.get('attention_required', [])),
            sum(1 for i in result.get('attention_required', []) if i.get('severity') == 'critical'),
            triggered_by,
        )
        return result
    finally:
        conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────

def init_scheduler(app):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import atexit

        def _job():
            with app.app_context():
                try:
                    run_briefing(triggered_by='scheduler')
                except Exception as exc:
                    logger.error("Scheduled briefing failed: %s", exc)

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(_job, trigger='cron', hour=6, minute=0,
                          id='daily_briefing', replace_existing=True)
        scheduler.start()
        atexit.register(scheduler.shutdown)
        logger.info("Briefing scheduler started — daily at 06:00")
        return scheduler
    except ImportError:
        logger.warning(
            "apscheduler not installed — scheduled briefings disabled. "
            "Run: pip install apscheduler"
        )
        return None


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    print("Running briefing...")
    result = run_briefing(triggered_by='manual')
    print(f"\nBriefing date: {result.get('briefing_date')}")
    print(f"Summary: {result.get('summary')}")
    print(f"Attention items: {len(result.get('attention_required', []))}")
    for item in result.get('attention_required', []):
        print(f"  [{item['severity'].upper()}] {item['batch_label']} — {item['issue']}")
