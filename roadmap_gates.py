"""
Roadmap auto-gate evaluation for the Mushroom Tracker.

evaluate_gates(db_path=None) -> dict[gate_key, dict]

Each value:
  {
    'status':    'on_track' | 'at_risk' | 'complete' | 'pending',
    'value':     <current measured value>,
    'threshold': <target description>,
    'detail':    <human-readable string>,
  }

Safe to call with an empty or missing database — returns 'pending' for all gates.
"""

from datetime import date, timedelta
import sqlite3


_PENDING_ALL = {
    k: {'status': 'pending', 'value': None, 'threshold': '—',
        'detail': 'No data yet.'}
    for k in ('contam_rate_15', 'contam_rate_10', 'be_baseline',
               'stagger_active', 'yield_3_5', 'yield_10_15', 'forecast_accuracy')
}


def _get_conn(db_path=None):
    if db_path is None:
        import mushroom_tracker as _mt
        path = str(_mt.DB_PATH)
    else:
        path = str(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _iso_week(d: date) -> tuple:
    iso = d.isocalendar()
    return (iso[0], iso[1])


def _abs_week(year: int, week: int) -> int:
    """Absolute week index from a fixed Monday reference — for consecutive-week checks."""
    d = date.fromisocalendar(year, week, 1)
    ref = date(2020, 1, 6)  # Monday of ISO 2020-W02
    return (d - ref).days // 7


# ── Individual gate evaluators ────────────────────────────────────────────────

def _eval_contam_rate(conn, threshold: float) -> dict:
    try:
        rows = conn.execute("""
            SELECT contamination_flag
            FROM batches
            WHERE inoculation_date >= date('now', '-90 days')
              AND inoculation_date IS NOT NULL
              AND (
                contamination_flag = 1
                OR status = 'done'
                OR inoculation_date <= date('now', '-14 days')
              )
        """).fetchall()
    except Exception:
        return {'status': 'pending', 'value': None,
                'threshold': f'<{threshold}%', 'detail': 'Database error.'}

    denom = len(rows)
    if denom == 0:
        return {
            'status': 'pending', 'value': None,
            'threshold': f'<{threshold}%',
            'detail': 'No batches with a known outcome yet (confirmed contaminated, done, or ≥14 days old).',
        }

    numer = sum(1 for r in rows if r['contamination_flag'])
    rate = numer / denom * 100

    if rate < threshold and denom >= 4:
        status = 'complete'
    elif rate < threshold and denom >= 2:
        status = 'on_track'
    else:
        status = 'at_risk'

    return {
        'status': status,
        'value': round(rate, 1),
        'threshold': f'<{threshold}%',
        'detail': (
            f'Contam rate: {rate:.1f}% ({numer}/{denom} batches). '
            f'Target: <{threshold}%. New batches excluded until confirmed contaminated, done, or ≥14 days old.'
        ),
    }


def _eval_be_baseline(conn) -> dict:
    try:
        rows = conn.execute("""
            SELECT species, COUNT(*) AS cnt
            FROM batches
            WHERE status = 'done' AND dry_weight_g IS NOT NULL
            GROUP BY species
            HAVING cnt >= 2
        """).fetchall()
    except Exception:
        return {'status': 'pending', 'value': 0,
                'threshold': '≥2 species', 'detail': 'Database error.'}

    count = len(rows)
    species_list = [r['species'] for r in rows]

    if count >= 2:
        status = 'complete'
    elif count == 1:
        status = 'on_track'
    else:
        status = 'pending'

    detail = (
        f'{count} species with ≥2 completed cycles: {", ".join(species_list)}.'
        if species_list else
        'No species has completed 2 full cycles yet.'
    )

    return {
        'status': status, 'value': count,
        'threshold': '≥2 species with ≥2 completed cycles',
        'detail': detail,
    }


def _eval_stagger_active(conn) -> dict:
    try:
        cutoff = str(date.today() - timedelta(weeks=8))
        rows = conn.execute("""
            SELECT harvest_date FROM flushes
            WHERE harvest_date >= ? AND harvest_date IS NOT NULL
        """, (cutoff,)).fetchall()
    except Exception:
        return {'status': 'pending', 'value': 0,
                'threshold': '4 of 8 weeks', 'detail': 'Database error.'}

    if not rows:
        return {
            'status': 'pending', 'value': 0,
            'threshold': '4 of 8 weeks with harvests',
            'detail': 'No harvests recorded in the last 8 weeks.',
        }

    harvest_weeks = set()
    for r in rows:
        try:
            d = date.fromisoformat(r['harvest_date'][:10])
            harvest_weeks.add(_iso_week(d))
        except Exception:
            pass

    # Build the set of last 8 ISO weeks
    today = date.today()
    last_8 = set()
    cursor = today
    while len(last_8) < 8:
        last_8.add(_iso_week(cursor))
        cursor -= timedelta(days=7)

    weeks_hit = len(harvest_weeks & last_8)

    if weeks_hit >= 6:
        status = 'complete'
    elif weeks_hit >= 4:
        status = 'on_track'
    else:
        status = 'at_risk'

    return {
        'status': status, 'value': weeks_hit,
        'threshold': '≥4 of 8 weeks (complete: ≥6)',
        'detail': f'{weeks_hit} of last 8 weeks had at least one harvest. Target: ≥4.',
    }


def _eval_yield_streak(conn, weekly_threshold_g: float, target_streak: int) -> dict:
    lb_str = f'{weekly_threshold_g / 453.592:.0f} lb'
    try:
        rows = conn.execute("""
            SELECT harvest_date, fresh_weight_g
            FROM flushes
            WHERE harvest_date IS NOT NULL AND fresh_weight_g IS NOT NULL
        """).fetchall()
    except Exception:
        return {
            'status': 'pending', 'value': 0,
            'threshold': f'{target_streak} weeks ≥ {lb_str}',
            'detail': 'Database error.',
        }

    if not rows:
        return {
            'status': 'pending', 'value': 0,
            'threshold': f'{target_streak} consecutive weeks ≥ {lb_str}',
            'detail': 'No flush data available.',
        }

    # Aggregate by ISO week in Python for correctness
    weekly: dict = {}
    for r in rows:
        try:
            d = date.fromisoformat(r['harvest_date'][:10])
            wk = _iso_week(d)
            weekly[wk] = weekly.get(wk, 0.0) + (r['fresh_weight_g'] or 0.0)
        except Exception:
            pass

    # Find longest streak of consecutive qualifying weeks
    sorted_weeks = sorted(weekly.keys(), key=lambda w: _abs_week(w[0], w[1]))

    max_streak = streak = 0
    prev_abs = None

    for wk in sorted_weeks:
        if weekly[wk] >= weekly_threshold_g:
            abs_w = _abs_week(wk[0], wk[1])
            if prev_abs is not None and abs_w == prev_abs + 1:
                streak += 1
            else:
                streak = 1
            prev_abs = abs_w
            max_streak = max(max_streak, streak)
        else:
            streak = 0
            prev_abs = None

    on_track_min = max(1, target_streak // 2)

    if max_streak >= target_streak:
        status = 'complete'
    elif max_streak >= on_track_min:
        status = 'on_track'
    elif max_streak > 0:
        status = 'at_risk'
    else:
        status = 'pending'

    return {
        'status': status, 'value': max_streak,
        'threshold': f'{target_streak} consecutive weeks ≥ {lb_str} ({weekly_threshold_g:.0f}g)',
        'detail': (
            f'Longest qualifying streak: {max_streak} consecutive week'
            f'{"s" if max_streak != 1 else ""} ≥ {lb_str}. '
            f'Target: {target_streak} weeks.'
        ),
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def evaluate_gates(db_path=None) -> dict:
    """
    Evaluate all auto-gate milestones against live DB data.
    Safe to call with an empty or missing DB — returns pending for all gates.
    """
    try:
        conn = _get_conn(db_path)
    except Exception:
        return dict(_PENDING_ALL)

    try:
        return {
            'contam_rate_15': _eval_contam_rate(conn, threshold=15.0),
            'contam_rate_10': _eval_contam_rate(conn, threshold=10.0),
            'be_baseline':    _eval_be_baseline(conn),
            'stagger_active': _eval_stagger_active(conn),
            'yield_3_5':      _eval_yield_streak(conn, weekly_threshold_g=1361.0, target_streak=4),
            'yield_10_15':    _eval_yield_streak(conn, weekly_threshold_g=4536.0, target_streak=8),
            'forecast_accuracy': {
                'status':    'pending',
                'value':     None,
                'threshold': '±20% for 4 consecutive weeks',
                'detail':    (
                    'Forecast accuracy tracking not yet implemented. '
                    'Mark complete manually when achieved.'
                ),
            },
        }
    finally:
        conn.close()
