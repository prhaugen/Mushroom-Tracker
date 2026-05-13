"""
Mushroom Tracker Web App v2
Run: python mushroom_app.py  →  http://localhost:5000
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3, json, os, csv, io
from pathlib import Path
from datetime import datetime, date, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))
import mushroom_tracker as _mt
from agent_config import SPECIES_TIMELINES
from mushroom_tracker import (init_db, bio_efficiency,
                               STATUSES, LIFECYCLE, SPAWN_TYPES,
                               STERIL_METHODS, DESTINATIONS, CHAMBER_TYPES,
                               SPECIES, next_batch_label, get_all_species,
                               get_substrate_other_options, get_spawn_source_options)

app = Flask(__name__)
app.secret_key = 'sgfc-mushroom-v2-2026'

_SPECIES_DEFAULTS = {
    sp: {
        'temp':        round((v['fruiting_temp_f'][0]      + v['fruiting_temp_f'][1])      / 2, 1),
        'humidity':    round((v['fruiting_humidity_rh'][0] + v['fruiting_humidity_rh'][1]) / 2, 1),
        'temp_lo':     v['fruiting_temp_f'][0],
        'temp_hi':     v['fruiting_temp_f'][1],
        'humidity_lo': v['fruiting_humidity_rh'][0],
        'humidity_hi': v['fruiting_humidity_rh'][1],
    }
    for sp, v in SPECIES_TIMELINES.items()
}

DB_PATH_PROD    = Path(__file__).parent / "mushroom_data.db"
DB_PATH_SANDBOX = Path(__file__).parent / "mushroom_data_sandbox.db"


def active_db_path():
    """Return the DB path for the current session (prod or sandbox)."""
    try:
        return DB_PATH_SANDBOX if session.get('db_mode') == 'sandbox' else DB_PATH_PROD
    except RuntimeError:
        return DB_PATH_PROD


def get_db():
    conn = sqlite3.connect(str(active_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


@app.before_request
def _sync_db_path():
    """Keep mushroom_tracker.DB_PATH in sync so init_db() hits the right file."""
    _mt.DB_PATH = active_db_path()


@app.context_processor
def _inject_db_mode():
    try:
        return {'db_mode': session.get('db_mode', 'prod')}
    except RuntimeError:
        return {'db_mode': 'prod'}


@app.route('/switch-db/<mode>')
def switch_db(mode):
    if mode == 'sandbox':
        session['db_mode'] = 'sandbox'
        _mt.DB_PATH = DB_PATH_SANDBOX
        _mt.init_db()
        flash('Switched to SANDBOX database. Changes here won\'t affect production.', 'warning')
    elif mode == 'prod':
        session['db_mode'] = 'prod'
        flash('Switched to PRODUCTION database.', 'success')
    return redirect(request.referrer or url_for('dashboard'))


def days_since(date_str):
    if not date_str: return None
    try: return (date.today() - datetime.strptime(date_str[:10], "%Y-%m-%d").date()).days
    except Exception: return None


def time_ago(ts_str):
    if not ts_str: return "never"
    try:
        delta = datetime.now() - datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
        m = int(delta.total_seconds() / 60)
        if m < 1: return "just now"
        if m < 60: return f"{m}m ago"
        if m < 1440: return f"{m//60}h ago"
        return f"{delta.days}d ago"
    except Exception: return str(ts_str)[:16]


def get_primary_chamber():
    conn = get_db()
    ch = conn.execute("SELECT * FROM chambers ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return ch


@app.context_processor
def ctx():
    conn = get_db()
    all_species = get_all_species(conn)
    substrate_other_opts = get_substrate_other_options(conn)
    spawn_source_opts = get_spawn_source_options(conn)
    conn.close()
    return dict(days_since=days_since, time_ago=time_ago, today=str(date.today()),
                now=datetime.now, bio_efficiency=bio_efficiency,
                STATUSES=STATUSES, LIFECYCLE=LIFECYCLE,
                SPAWN_TYPES=SPAWN_TYPES, STERIL_METHODS=STERIL_METHODS,
                DESTINATIONS=DESTINATIONS, SPECIES=all_species,
                SUBSTRATE_OTHER_OPTIONS=substrate_other_opts,
                SPAWN_SOURCE_OPTIONS=spawn_source_opts)


# ── Legacy redirects ──────────────────────────────────────────────────────────
@app.route('/blocks')
def _redir_blocks(): return redirect(url_for('batches'))
@app.route('/block/add')
def _redir_block_add(): return redirect(url_for('batch_add'))
@app.route('/block/<int:bid>')
def _redir_block(bid): return redirect(url_for('batch_detail', batch_id=bid))
@app.route('/harvest/log/<int:bid>')
def _redir_harvest(bid): return redirect(url_for('flush_add', batch_id=bid))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/')
def dashboard():
    init_db()
    conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers").fetchall()
    if not chambers:
        conn.close(); return redirect(url_for('setup'))

    chamber = dict(chambers[0])
    latest_env = conn.execute(
        "SELECT * FROM environment_logs WHERE chamber_id=? ORDER BY logged_at DESC LIMIT 1",
        (chamber['id'],)).fetchone()
    batches = conn.execute(
        "SELECT * FROM batches WHERE chamber_id=? ORDER BY id", (chamber['id'],)).fetchall()
    recent_flushes = conn.execute("""
        SELECT f.*, b.label, b.species FROM flushes f
        JOIN batches b ON f.batch_id=b.id
        ORDER BY f.created_at DESC LIMIT 6
    """).fetchall()

    total_yield  = sum(b['total_yield_g'] for b in batches)
    active_count = sum(1 for b in batches if b['status'] not in ('done','contaminated','aborted'))
    env_count    = conn.execute(
        "SELECT COUNT(*) FROM environment_logs WHERE chamber_id=?", (chamber['id'],)).fetchone()[0]
    first_inoc   = min((b['inoculation_date'] for b in batches if b['inoculation_date']), default=None)
    days_running = days_since(first_inoc)

    # avg BE across batches that have dry_weight_g set
    be_list = [bio_efficiency(b['total_yield_g'], b['dry_weight_g'])
               for b in batches if b['dry_weight_g']]
    avg_be = round(sum(be_list)/len(be_list), 1) if be_list else None

    conn.close()
    return render_template('dashboard.html',
        chamber=chamber, latest_env=latest_env, batches=batches,
        recent_flushes=recent_flushes, total_yield=total_yield,
        active_count=active_count, env_count=env_count,
        days_running=days_running, avg_be=avg_be)


# ── Setup ─────────────────────────────────────────────────────────────────────
@app.route('/setup', methods=['GET','POST'])
def setup():
    init_db()
    if request.method == 'POST':
        conn = get_db()
        conn.execute(
            "INSERT INTO chambers(name,location,chamber_type,target_temp_f,target_humidity_rh,notes) VALUES(?,?,?,?,?,?)",
            (request.form.get('name') or 'SGFC-1',
             request.form.get('location') or 'Basement',
             request.form.get('chamber_type') or None,
             float(request.form.get('target_temp') or 72),
             float(request.form.get('target_humidity') or 90),
             request.form.get('notes') or None))
        conn.commit(); conn.close()
        flash('Chamber created — add your first batch to get started.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('setup.html', chamber_types=CHAMBER_TYPES)


# ── Label API ─────────────────────────────────────────────────────────────────
@app.route('/api/next-label')
def api_next_label():
    species = request.args.get('species', '').strip()
    if not species:
        return jsonify({'label': ''})
    conn = get_db()
    label = next_batch_label(conn, species)
    conn.close()
    return jsonify({'label': label})


# ── Batches ───────────────────────────────────────────────────────────────────
@app.route('/batches')
def batches():
    init_db()
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, c.name chamber_name FROM batches b
        LEFT JOIN chambers c ON b.chamber_id=c.id ORDER BY b.id
    """).fetchall()
    conn.close()
    return render_template('batches.html', batches=rows)


@app.route('/batch/add', methods=['GET','POST'])
def batch_add():
    init_db()
    conn = get_db()
    chamber = get_primary_chamber()
    if not chamber: conn.close(); return redirect(url_for('setup'))
    all_chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    conn.close()

    if request.method == 'POST':
        f = request.form
        species = f.get('species_custom','').strip() if f.get('species') == '__other__' else f.get('species','')
        conn = get_db()
        if f.get('species') == '__other__' and species:
            conn.execute("INSERT OR IGNORE INTO custom_species(name) VALUES(?)", (species,))
        substrate_other = f.get('substrate_other', '').strip() or None
        if substrate_other:
            conn.execute("INSERT OR IGNORE INTO custom_substrate_other(value) VALUES(?)", (substrate_other,))
        spawn_source = f.get('spawn_source', '').strip() or None
        if spawn_source:
            conn.execute("INSERT OR IGNORE INTO custom_spawn_source(value) VALUES(?)", (spawn_source,))
        conn.execute("""INSERT INTO batches
            (chamber_id,colonization_chamber_id,label,species,strain,
             target_temp_f,target_humidity_rh,
             dry_weight_g,moisture_pct,straw_pct,hardwood_pct,bran_pct,gypsum_pct,coco_pct,
             substrate_other,substrate_notes,
             steril_method,steril_temp_f,steril_duration_min,
             inoculation_date,spawn_type,spawn_strain,spawn_rate_pct,spawn_source,spawn_lot,
             colonization_start_date,fruiting_start_date,sourced_block,status,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (chamber['id'],
             int(f['colonization_chamber_id']) if f.get('colonization_chamber_id') else None,
             f['label'], species, f.get('strain') or None,
             float(f.get('target_temp') or 72), float(f.get('target_humidity') or 90),
             float(f['dry_weight_g']) if f.get('dry_weight_g') else None,
             float(f['moisture_pct']) if f.get('moisture_pct') else None,
             float(f.get('straw_pct') or 0), float(f.get('hardwood_pct') or 0),
             float(f.get('bran_pct') or 0), float(f.get('gypsum_pct') or 0),
             float(f.get('coco_pct') or 0), substrate_other,
             f.get('substrate_notes') or None,
             f.get('steril_method') or None,
             float(f['steril_temp_f']) if f.get('steril_temp_f') else None,
             int(f['steril_duration_min']) if f.get('steril_duration_min') else None,
             f.get('inoculation_date') or str(date.today()),
             f.get('spawn_type') or None, f.get('spawn_strain') or None,
             float(f['spawn_rate_pct']) if f.get('spawn_rate_pct') else None,
             spawn_source, f.get('spawn_lot') or None,
             f.get('inoculation_date') or str(date.today()),
             f.get('fruiting_start_date') or None,
             1 if f.get('sourced_block') else 0,
             f.get('status','colonizing'), f.get('notes') or None))
        conn.commit(); conn.close()
        flash(f"Batch '{f['label']}' added.", 'success')
        return redirect(url_for('batches'))

    return render_template('batch_form.html', chamber=chamber, batch=None, all_chambers=all_chambers,
                           species_defaults=json.dumps(_SPECIES_DEFAULTS))


@app.route('/batch/<int:batch_id>')
def batch_detail(batch_id):
    init_db()
    conn = get_db()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        flash('Batch not found.', 'error'); conn.close()
        return redirect(url_for('batches'))
    flushes = conn.execute(
        "SELECT * FROM flushes WHERE batch_id=? ORDER BY flush_number", (batch_id,)).fetchall()
    sales = conn.execute("""
        SELECT s.*, f.flush_number FROM sales s
        LEFT JOIN flushes f ON s.flush_id=f.id
        WHERE s.batch_id=? ORDER BY s.sale_date DESC
    """, (batch_id,)).fetchall()
    yield_chart = [{'flush': f['flush_number'], 'weight': f['fresh_weight_g'],
                    'quality': f['quality_rating']} for f in flushes]
    cycle_days = None
    if batch['block_end_date'] and batch['inoculation_date']:
        try:
            d1 = date.fromisoformat(batch['inoculation_date'][:10])
            d2 = date.fromisoformat(batch['block_end_date'][:10])
            cycle_days = (d2 - d1).days
        except Exception:
            pass
    sp_key = batch['species'].lower() if batch['species'] else None
    sp_defaults = _SPECIES_DEFAULTS.get(sp_key)
    targets_customized = None
    if sp_defaults and batch['target_temp_f'] is not None and batch['target_humidity_rh'] is not None:
        targets_customized = (
            abs(batch['target_temp_f'] - sp_defaults['temp']) > 0.1 or
            abs(batch['target_humidity_rh'] - sp_defaults['humidity']) > 0.1
        )

    # Environment chart scoped to this batch's active period
    try:
        env_res = int(request.args.get('res', 0))
        if env_res not in _ENV_RESOLUTIONS:
            env_res = 0
    except (ValueError, TypeError):
        env_res = 0

    chart_start = batch['inoculation_date'] or batch['colonization_start_date']
    chart_end   = batch['block_end_date'] or str(date.today())
    try:
        cs_dt = datetime.strptime(chart_start[:10], '%Y-%m-%d')
        ce_dt = datetime.strptime(chart_end[:10],   '%Y-%m-%d') + timedelta(days=1)
    except Exception:
        cs_dt = datetime.now() - timedelta(days=7)
        ce_dt = datetime.now()

    span_days = max((ce_dt - cs_dt).days, 1)
    if env_res == 0:
        if   span_days <= 2:  env_res = 5
        elif span_days <= 7:  env_res = 10
        elif span_days <= 21: env_res = 30
        else:                 env_res = 60

    env_rows = conn.execute("""
        SELECT logged_at, temp_f, humidity_rh
        FROM environment_logs
        WHERE chamber_id = ? AND logged_at >= ? AND logged_at <= ?
        ORDER BY logged_at ASC
    """, (batch['chamber_id'],
          cs_dt.strftime('%Y-%m-%d %H:%M:%S'),
          ce_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    env_agg = _aggregate_env_logs([dict(r) for r in env_rows], env_res)

    batch_chart_data = {
        'labels':      [r['logged_at'][:16] for r in env_agg],
        'temp':        [r['temp_f']          for r in env_agg],
        'humidity':    [r['humidity_rh']     for r in env_agg],
        'target_temp': batch['target_temp_f'],
        'target_hum':  batch['target_humidity_rh'],
        'temp_lo':     sp_defaults['temp_lo']     if sp_defaults else None,
        'temp_hi':     sp_defaults['temp_hi']     if sp_defaults else None,
        'humidity_lo': sp_defaults['humidity_lo'] if sp_defaults else None,
        'humidity_hi': sp_defaults['humidity_hi'] if sp_defaults else None,
    }

    conn.close()
    return render_template('batch_detail.html',
        batch=batch, flushes=flushes, sales=sales, yield_chart=yield_chart,
        cycle_days=cycle_days, sp_defaults=sp_defaults, targets_customized=targets_customized,
        batch_chart_data=batch_chart_data, env_res=env_res, resolutions=_ENV_RESOLUTIONS)


@app.route('/batch/<int:batch_id>/update', methods=['POST'])
def batch_update(batch_id):
    conn = get_db()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        conn.close(); flash('Batch not found.','error')
        return redirect(url_for('batches'))
    f = request.form
    new_status = f.get('status', batch['status'])
    updates = {'status': new_status}
    today = str(date.today())
    if new_status == 'colonized' and not batch['colonization_end_date']:
        updates['colonization_end_date'] = today
    if new_status == 'pinning':
        updates['pinning_started_at'] = today
    if new_status == 'done' and not batch['block_end_date']:
        updates['block_end_date'] = today
    if new_status == 'contaminated':
        updates['contamination_flag'] = 1
        if f.get('contamination_type'):
            updates['contamination_type'] = f['contamination_type']
    if new_status == 'aborted':
        updates['abort_flag'] = 1; updates['abort_date'] = today
    if f.get('notes'): updates['notes'] = f['notes']
    sql = ', '.join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE batches SET {sql} WHERE id=?", (*updates.values(), batch_id))
    conn.commit(); conn.close()
    flash(f"Status updated to '{new_status}'.", 'success')
    return redirect(url_for('batch_detail', batch_id=batch_id))


# ── Flushes ───────────────────────────────────────────────────────────────────
@app.route('/batch/<int:batch_id>/flush/add', methods=['GET','POST'])
def flush_add(batch_id):
    init_db()
    conn = get_db()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        conn.close(); flash('Batch not found.','error')
        return redirect(url_for('batches'))
    if request.method == 'POST':
        f = request.form
        flush_num = int(f['flush_number'])
        weight_g  = float(f['weight_g'])
        conn.execute("""INSERT INTO flushes
            (batch_id,flush_number,pinning_date,harvest_date,fresh_weight_g,quality_rating,notes)
            VALUES(?,?,?,?,?,?,?)""",
            (batch_id, flush_num,
             f.get('pinning_date') or None,
             f.get('harvest_date') or str(date.today()),
             weight_g,
             int(f['quality_rating']) if f.get('quality_rating') else None,
             f.get('notes') or None))
        conn.execute(
            "UPDATE batches SET total_flushes=?, total_yield_g=total_yield_g+?, status='resting' WHERE id=?",
            (flush_num, weight_g, batch_id))
        conn.commit(); conn.close()
        flash(f"Flush #{flush_num} logged: {weight_g:.0f}g.", 'success')
        return redirect(url_for('batch_detail', batch_id=batch_id))
    next_flush = batch['total_flushes'] + 1
    default_pinning_date = batch['pinning_started_at'] or ''
    conn.close()
    return render_template('flush_form.html', batch=batch, next_flush=next_flush,
                           default_pinning_date=default_pinning_date)


# ── Sales ─────────────────────────────────────────────────────────────────────
@app.route('/sales')
def sales_list():
    init_db()
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, b.label, b.species, f.flush_number
        FROM sales s
        JOIN batches b ON s.batch_id=b.id
        LEFT JOIN flushes f ON s.flush_id=f.id
        ORDER BY s.sale_date DESC
    """).fetchall()
    total_revenue = sum((r['price_per_lb'] or 0) * (r['fresh_weight_sold_g'] or 0) / 453.592
                        for r in rows)
    conn.close()
    return render_template('sales_list.html', sales=rows, total_revenue=total_revenue)


@app.route('/sales/add', methods=['GET','POST'])
@app.route('/sales/add/<int:batch_id>', methods=['GET','POST'])
def sales_add(batch_id=None):
    init_db()
    conn = get_db()
    all_batches = conn.execute("SELECT id,label,species FROM batches ORDER BY id").fetchall()
    selected_batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone() if batch_id else None
    flushes_for_batch = []
    if batch_id:
        flushes_for_batch = conn.execute(
            "SELECT * FROM flushes WHERE batch_id=? ORDER BY flush_number", (batch_id,)).fetchall()

    if request.method == 'POST':
        f = request.form
        bid = int(f['batch_id'])
        fresh_g = float(f['fresh_weight_sold_g']) if f.get('fresh_weight_sold_g') else None
        dried_g = float(f['dried_weight_sold_g']) if f.get('dried_weight_sold_g') else None
        conn.execute("""INSERT INTO sales
            (batch_id,flush_id,sale_date,destination,customer,
             fresh_weight_sold_g,dried_weight_sold_g,price_per_lb,notes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (bid,
             int(f['flush_id']) if f.get('flush_id') else None,
             f.get('sale_date') or str(date.today()),
             f.get('destination') or None,
             f.get('customer') or None,
             fresh_g, dried_g,
             float(f['price_per_lb']) if f.get('price_per_lb') else None,
             f.get('notes') or None))
        conn.commit(); conn.close()
        flash('Sale recorded.', 'success')
        return redirect(url_for('sales_list'))

    conn.close()
    return render_template('sales_form.html',
        all_batches=all_batches, selected_batch=selected_batch,
        flushes_for_batch=flushes_for_batch)


# ── Environment ───────────────────────────────────────────────────────────────
@app.route('/env/log', methods=['GET','POST'])
def env_log():
    init_db()
    chamber = get_primary_chamber()
    if not chamber: return redirect(url_for('setup'))
    conn = get_db()
    active_batches = conn.execute(
        "SELECT id,label,species FROM batches WHERE status NOT IN ('done','contaminated','aborted') ORDER BY id"
    ).fetchall()

    if request.method == 'POST':
        f = request.form
        conn.execute("""INSERT INTO environment_logs
            (chamber_id,batch_id,phase,temp_f,humidity_rh,co2_ppm,
             fae_fan_cycles_day,light_hours,misting_count,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (chamber['id'],
             int(f['batch_id']) if f.get('batch_id') else None,
             f.get('phase','fruiting'),
             float(f['temp_f']), float(f['humidity_rh']),
             float(f['co2_ppm']) if f.get('co2_ppm') else None,
             int(f['fae_fan_cycles_day']) if f.get('fae_fan_cycles_day') else None,
             float(f['light_hours']) if f.get('light_hours') else None,
             int(f['misting_count']) if f.get('misting_count') else None,
             f.get('notes') or None))
        conn.commit(); conn.close()
        flash('Environment reading saved.', 'success')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('env_log.html', chamber=chamber, active_batches=active_batches, log=None)


_ENV_RESOLUTIONS = (1, 5, 10, 30, 60)

def _aggregate_env_logs(rows, bucket_min):
    """Average readings into fixed-size time buckets. Returns list of dicts."""
    if bucket_min <= 1:
        return [dict(r) for r in rows]
    from math import floor
    buckets = {}
    for row in rows:
        try:
            dt  = datetime.strptime(str(row['logged_at'])[:19], '%Y-%m-%d %H:%M:%S')
            # Floor to bucket boundary using minutes-since-epoch (local, no tz needed)
            epoch_min   = int(dt.timestamp()) // 60
            bucket_min_ = (epoch_min // bucket_min) * bucket_min
            bucket_dt   = datetime.fromtimestamp(bucket_min_ * 60)
            key         = bucket_dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            continue
        if key not in buckets:
            buckets[key] = {'temp': [], 'hum': [], 'co2': []}
        if row['temp_f']      is not None: buckets[key]['temp'].append(row['temp_f'])
        if row['humidity_rh'] is not None: buckets[key]['hum'].append(row['humidity_rh'])
        if row['co2_ppm']     is not None: buckets[key]['co2'].append(row['co2_ppm'])
    result = []
    for key in sorted(buckets):
        b = buckets[key]
        result.append({
            'logged_at':   key,
            'temp_f':      round(sum(b['temp']) / len(b['temp']), 1) if b['temp'] else None,
            'humidity_rh': round(sum(b['hum'])  / len(b['hum']),  1) if b['hum']  else None,
            'co2_ppm':     round(sum(b['co2'])  / len(b['co2']),  0) if b['co2']  else None,
        })
    return result


@app.route('/env/history')
def env_history():
    init_db()
    chamber = get_primary_chamber()
    if not chamber: return redirect(url_for('setup'))

    now = datetime.now()
    default_start = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
    default_end   = now.strftime('%Y-%m-%dT%H:%M')

    start_str = request.args.get('start', default_start)
    end_str   = request.args.get('end',   default_end)
    try:
        res = int(request.args.get('res', 5))
        if res not in _ENV_RESOLUTIONS:
            res = 5
    except (ValueError, TypeError):
        res = 5

    try:
        start_dt = datetime.strptime(start_str[:16], '%Y-%m-%dT%H:%M')
        end_dt   = datetime.strptime(end_str[:16],   '%Y-%m-%dT%H:%M')
    except ValueError:
        start_dt  = now - timedelta(hours=24)
        end_dt    = now
        start_str = start_dt.strftime('%Y-%m-%dT%H:%M')
        end_str   = end_dt.strftime('%Y-%m-%dT%H:%M')

    start_db = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_db   = end_dt.strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    logs = conn.execute("""
        SELECT e.*, b.label batch_label FROM environment_logs e
        LEFT JOIN batches b ON e.batch_id=b.id
        WHERE e.chamber_id=? ORDER BY e.logged_at DESC
    """, (chamber['id'],)).fetchall()

    chart_rows = conn.execute("""
        SELECT logged_at, temp_f, humidity_rh, co2_ppm
        FROM environment_logs
        WHERE chamber_id = ? AND logged_at >= ? AND logged_at <= ?
        ORDER BY logged_at ASC
    """, (chamber['id'], start_db, end_db)).fetchall()
    chart_rows = _aggregate_env_logs([dict(r) for r in chart_rows], res)

    recent_batch = conn.execute("""
        SELECT b.target_temp_f, b.target_humidity_rh, b.label, b.species
        FROM environment_logs e
        JOIN batches b ON e.batch_id = b.id
        WHERE e.chamber_id = ?
        ORDER BY e.logged_at DESC LIMIT 1
    """, (chamber['id'],)).fetchone()
    chart_data = {
        'labels':          [r['logged_at'][:16] for r in chart_rows],
        'temp':            [r['temp_f']      for r in chart_rows],
        'humidity':        [r['humidity_rh'] for r in chart_rows],
        'target_temp':     recent_batch['target_temp_f']      if recent_batch else chamber['target_temp_f'],
        'target_humidity': recent_batch['target_humidity_rh'] if recent_batch else chamber['target_humidity_rh'],
        'target_batch':    f"{recent_batch['label']} ({recent_batch['species']})" if recent_batch else None,
    }
    conn.close()
    return render_template('env_history.html', chamber=chamber, logs=logs,
                           chart_data=chart_data,
                           start_str=start_str, end_str=end_str,
                           res=res, resolutions=_ENV_RESOLUTIONS)


# ── Report ────────────────────────────────────────────────────────────────────
@app.route('/report')
def report():
    init_db()
    conn = get_db()
    batches = conn.execute("SELECT * FROM batches ORDER BY id").fetchall()
    all_flushes = conn.execute("""
        SELECT f.*, b.label, b.species, b.dry_weight_g FROM flushes f
        JOIN batches b ON f.batch_id=b.id ORDER BY b.id, f.flush_number
    """).fetchall()

    # Build flush degradation chart: one dataset per batch
    batch_map = {b['id']: b for b in batches}
    max_flush = max((f['flush_number'] for f in all_flushes), default=0)
    COLORS = ['#3fb950','#58a6ff','#bc8cff','#ff7b72','#d29922','#39d353','#f0883e']
    degradation_datasets = []
    for i, b in enumerate(batches):
        b_flushes = [f for f in all_flushes if f['batch_id'] == b['id']]
        if not b_flushes: continue
        flush_map = {f['flush_number']: f['fresh_weight_g'] for f in b_flushes}
        data = [flush_map.get(n) for n in range(1, max_flush + 1)]
        col = COLORS[i % len(COLORS)]
        degradation_datasets.append({
            'label': b['label'],
            'data': data,
            'borderColor': col,
            'backgroundColor': col + '22',
            'tension': 0.3, 'pointRadius': 5,
            'spanGaps': True,
        })

    # Yield bar chart: stacked by flush
    bar_datasets = []
    for fi in range(1, max_flush + 1):
        weights = []
        for b in batches:
            fdata = next((f for f in all_flushes if f['batch_id']==b['id'] and f['flush_number']==fi), None)
            weights.append(fdata['fresh_weight_g'] if fdata else 0)
        col = COLORS[(fi-1) % len(COLORS)]
        bar_datasets.append({'label': f'Flush {fi}', 'data': weights,
                              'backgroundColor': col+'99', 'borderColor': col, 'borderWidth':1})

    # BE ranking
    be_ranking = sorted(
        [(b, bio_efficiency(b['total_yield_g'], b['dry_weight_g'])) for b in batches],
        key=lambda x: (x[1] or -1), reverse=True)

    # Sales summary
    sales = conn.execute("""
        SELECT s.*, b.label, b.species FROM sales s
        JOIN batches b ON s.batch_id=b.id ORDER BY s.sale_date DESC
    """).fetchall()
    total_revenue = sum((s['price_per_lb'] or 0) * (s['fresh_weight_sold_g'] or 0) / 453.592
                        for s in sales)
    total_sold_fresh = sum(s['fresh_weight_sold_g'] or 0 for s in sales)
    total_sold_dried  = sum(s['dried_weight_sold_g'] or 0 for s in sales)

    env_stats = conn.execute("""
        SELECT AVG(temp_f) at, MIN(temp_f) nt, MAX(temp_f) xt,
               AVG(humidity_rh) ah, MIN(humidity_rh) nh, MAX(humidity_rh) xh,
               COUNT(*) cnt FROM environment_logs
    """).fetchone()

    total_yield = sum(b['total_yield_g'] for b in batches)
    conn.close()
    return render_template('report.html',
        batches=batches, all_flushes=all_flushes,
        be_ranking=be_ranking,
        bar_chart={'labels': [b['label'] for b in batches], 'datasets': bar_datasets},
        degradation_chart={'datasets': degradation_datasets,
                           'labels': [f'Flush {i}' for i in range(1, max_flush+1)]},
        env_stats=env_stats, total_yield=total_yield,
        sales=sales, total_revenue=total_revenue,
        total_sold_fresh=total_sold_fresh, total_sold_dried=total_sold_dried)


# ── Edit & Delete ─────────────────────────────────────────────────────────────

@app.route('/setup/edit', methods=['GET','POST'])
def chamber_edit():
    chamber = get_primary_chamber()
    if not chamber: return redirect(url_for('setup'))
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        conn.execute(
            "UPDATE chambers SET name=?,location=?,chamber_type=?,target_temp_f=?,target_humidity_rh=?,notes=? WHERE id=?",
            (f.get('name') or 'SGFC-1', f.get('location') or '',
             f.get('chamber_type') or None,
             float(f.get('target_temp') or 72), float(f.get('target_humidity') or 90),
             f.get('notes') or None, chamber['id']))
        conn.commit(); conn.close()
        flash('Chamber settings updated.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('chamber_edit.html', chamber=chamber, chamber_types=CHAMBER_TYPES)


@app.route('/batch/<int:batch_id>/edit', methods=['GET','POST'])
def batch_edit(batch_id):
    conn = get_db()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        conn.close(); flash('Batch not found.','error')
        return redirect(url_for('batches'))
    chamber = get_primary_chamber()
    all_chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    if request.method == 'POST':
        f = request.form
        species = f.get('species_custom','').strip() if f.get('species') == '__other__' else f.get('species','')
        if f.get('species') == '__other__' and species:
            conn.execute("INSERT OR IGNORE INTO custom_species(name) VALUES(?)", (species,))
        substrate_other = f.get('substrate_other', '').strip() or None
        if substrate_other:
            conn.execute("INSERT OR IGNORE INTO custom_substrate_other(value) VALUES(?)", (substrate_other,))
        spawn_source = f.get('spawn_source', '').strip() or None
        if spawn_source:
            conn.execute("INSERT OR IGNORE INTO custom_spawn_source(value) VALUES(?)", (spawn_source,))
        conn.execute("""UPDATE batches SET
            label=?,species=?,strain=?,
            colonization_chamber_id=?,
            target_temp_f=?,target_humidity_rh=?,
            dry_weight_g=?,moisture_pct=?,straw_pct=?,hardwood_pct=?,bran_pct=?,
            gypsum_pct=?,coco_pct=?,substrate_other=?,substrate_notes=?,
            steril_method=?,steril_temp_f=?,steril_duration_min=?,
            inoculation_date=?,spawn_type=?,spawn_strain=?,spawn_rate_pct=?,
            spawn_source=?,spawn_lot=?,fruiting_start_date=?,sourced_block=?,notes=?
            WHERE id=?""",
            (f['label'], species, f.get('strain') or None,
             int(f['colonization_chamber_id']) if f.get('colonization_chamber_id') else None,
             float(f.get('target_temp') or 72), float(f.get('target_humidity') or 90),
             float(f['dry_weight_g']) if f.get('dry_weight_g') else None,
             float(f['moisture_pct']) if f.get('moisture_pct') else None,
             float(f.get('straw_pct') or 0), float(f.get('hardwood_pct') or 0),
             float(f.get('bran_pct') or 0), float(f.get('gypsum_pct') or 0),
             float(f.get('coco_pct') or 0), substrate_other,
             f.get('substrate_notes') or None,
             f.get('steril_method') or None,
             float(f['steril_temp_f']) if f.get('steril_temp_f') else None,
             int(f['steril_duration_min']) if f.get('steril_duration_min') else None,
             f.get('inoculation_date') or str(date.today()),
             f.get('spawn_type') or None, f.get('spawn_strain') or None,
             float(f['spawn_rate_pct']) if f.get('spawn_rate_pct') else None,
             spawn_source, f.get('spawn_lot') or None,
             f.get('fruiting_start_date') or None,
             1 if f.get('sourced_block') else 0,
             f.get('notes') or None, batch_id))
        conn.commit(); conn.close()
        flash(f"Batch '{f['label']}' updated.", 'success')
        return redirect(url_for('batch_detail', batch_id=batch_id))
    conn.close()
    return render_template('batch_form.html', chamber=chamber, batch=batch, all_chambers=all_chambers,
                           species_defaults=json.dumps(_SPECIES_DEFAULTS))


@app.route('/batch/<int:batch_id>/delete', methods=['POST'])
def batch_delete(batch_id):
    conn = get_db()
    batch = conn.execute("SELECT label FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        conn.close(); flash('Batch not found.','error')
        return redirect(url_for('batches'))
    label = batch['label']
    conn.execute("DELETE FROM sales WHERE batch_id=?", (batch_id,))
    conn.execute("DELETE FROM flushes WHERE batch_id=?", (batch_id,))
    conn.execute("UPDATE environment_logs SET batch_id=NULL WHERE batch_id=?", (batch_id,))
    conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
    conn.commit(); conn.close()
    flash(f"Batch '{label}' and all its flushes and sales have been deleted.", 'success')
    return redirect(url_for('batches'))


@app.route('/flush/<int:flush_id>/edit', methods=['GET','POST'])
def flush_edit(flush_id):
    conn = get_db()
    flush = conn.execute("SELECT * FROM flushes WHERE id=?", (flush_id,)).fetchone()
    if not flush:
        conn.close(); flash('Flush not found.','error')
        return redirect(url_for('batches'))
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (flush['batch_id'],)).fetchone()
    if request.method == 'POST':
        f = request.form
        conn.execute("""UPDATE flushes SET
            flush_number=?,pinning_date=?,harvest_date=?,
            fresh_weight_g=?,quality_rating=?,notes=?
            WHERE id=?""",
            (int(f['flush_number']),
             f.get('pinning_date') or None,
             f.get('harvest_date') or str(date.today()),
             float(f['weight_g']),
             int(f['quality_rating']) if f.get('quality_rating') else None,
             f.get('notes') or None, flush_id))
        totals = conn.execute(
            "SELECT COUNT(*) cnt, COALESCE(SUM(fresh_weight_g),0) total FROM flushes WHERE batch_id=?",
            (flush['batch_id'],)).fetchone()
        conn.execute("UPDATE batches SET total_flushes=?,total_yield_g=? WHERE id=?",
            (totals['cnt'], totals['total'], flush['batch_id']))
        conn.commit(); conn.close()
        flash(f"Flush #{f['flush_number']} updated.", 'success')
        return redirect(url_for('batch_detail', batch_id=flush['batch_id']))
    conn.close()
    return render_template('flush_form.html', batch=batch,
                           next_flush=flush['flush_number'], flush=flush)


@app.route('/flush/<int:flush_id>/delete', methods=['POST'])
def flush_delete(flush_id):
    conn = get_db()
    flush = conn.execute("SELECT * FROM flushes WHERE id=?", (flush_id,)).fetchone()
    if not flush:
        conn.close(); flash('Flush not found.','error')
        return redirect(url_for('batches'))
    batch_id, num = flush['batch_id'], flush['flush_number']
    conn.execute("DELETE FROM flushes WHERE id=?", (flush_id,))
    totals = conn.execute(
        "SELECT COUNT(*) cnt, COALESCE(SUM(fresh_weight_g),0) total FROM flushes WHERE batch_id=?",
        (batch_id,)).fetchone()
    conn.execute("UPDATE batches SET total_flushes=?,total_yield_g=? WHERE id=?",
        (totals['cnt'], totals['total'], batch_id))
    conn.commit(); conn.close()
    flash(f"Flush #{num} deleted and batch totals recalculated.", 'success')
    return redirect(url_for('batch_detail', batch_id=batch_id))


@app.route('/env/<int:log_id>/edit', methods=['GET','POST'])
def env_edit(log_id):
    chamber = get_primary_chamber()
    conn = get_db()
    log = conn.execute("SELECT * FROM environment_logs WHERE id=?", (log_id,)).fetchone()
    if not log:
        conn.close(); flash('Reading not found.','error')
        return redirect(url_for('env_history'))
    active_batches = conn.execute("SELECT id,label,species FROM batches ORDER BY id").fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute("""UPDATE environment_logs SET
            batch_id=?,phase=?,temp_f=?,humidity_rh=?,co2_ppm=?,
            fae_fan_cycles_day=?,light_hours=?,misting_count=?,notes=?
            WHERE id=?""",
            (int(f['batch_id']) if f.get('batch_id') else None,
             f.get('phase','fruiting'),
             float(f['temp_f']), float(f['humidity_rh']),
             float(f['co2_ppm']) if f.get('co2_ppm') else None,
             int(f['fae_fan_cycles_day']) if f.get('fae_fan_cycles_day') else None,
             float(f['light_hours']) if f.get('light_hours') else None,
             int(f['misting_count']) if f.get('misting_count') else None,
             f.get('notes') or None, log_id))
        conn.commit(); conn.close()
        flash('Environment reading updated.', 'success')
        return redirect(url_for('env_history'))
    conn.close()
    return render_template('env_log.html', chamber=chamber,
                           active_batches=active_batches, log=log)


@app.route('/env/<int:log_id>/delete', methods=['POST'])
def env_delete(log_id):
    conn = get_db()
    conn.execute("DELETE FROM environment_logs WHERE id=?", (log_id,))
    conn.commit(); conn.close()
    flash('Environment reading deleted.', 'success')
    return redirect(url_for('env_history'))


@app.route('/sales/<int:sale_id>/edit', methods=['GET','POST'])
def sale_edit(sale_id):
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    if not sale:
        conn.close(); flash('Sale not found.','error')
        return redirect(url_for('sales_list'))
    all_batches = conn.execute("SELECT id,label,species FROM batches ORDER BY id").fetchall()
    flushes_for_batch = conn.execute(
        "SELECT * FROM flushes WHERE batch_id=? ORDER BY flush_number",
        (sale['batch_id'],)).fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute("""UPDATE sales SET
            batch_id=?,flush_id=?,sale_date=?,
            destination=?,customer=?,
            fresh_weight_sold_g=?,dried_weight_sold_g=?,
            price_per_lb=?,notes=?
            WHERE id=?""",
            (int(f['batch_id']),
             int(f['flush_id']) if f.get('flush_id') else None,
             f.get('sale_date') or str(date.today()),
             f.get('destination') or None,
             f.get('customer') or None,
             float(f['fresh_weight_sold_g']) if f.get('fresh_weight_sold_g') else None,
             float(f['dried_weight_sold_g']) if f.get('dried_weight_sold_g') else None,
             float(f['price_per_lb']) if f.get('price_per_lb') else None,
             f.get('notes') or None, sale_id))
        conn.commit(); conn.close()
        flash('Sale updated.', 'success')
        return redirect(url_for('sales_list'))
    conn.close()
    return render_template('sales_form.html',
        all_batches=all_batches, selected_batch=None,
        flushes_for_batch=flushes_for_batch, sale=sale)


@app.route('/sales/<int:sale_id>/delete', methods=['POST'])
def sale_delete(sale_id):
    conn = get_db()
    conn.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    conn.commit(); conn.close()
    flash('Sale deleted.', 'success')
    return redirect(url_for('sales_list'))


# ── Briefing ──────────────────────────────────────────────────────────────────

@app.route('/briefing')
@app.route('/briefing/<briefing_date>')
def briefing(briefing_date=None):
    init_db()
    conn = get_db()
    history = conn.execute("""
        SELECT briefing_date, attention_count, critical_count,
               generated_at, triggered_by
        FROM daily_briefings
        ORDER BY briefing_date DESC
        LIMIT 7
    """).fetchall()
    target_date = briefing_date or (history[0]['briefing_date'] if history else str(date.today()))
    record = conn.execute(
        "SELECT * FROM daily_briefings WHERE briefing_date = ?", (target_date,)
    ).fetchone()
    conn.close()
    briefing_data = None
    if record:
        try:
            briefing_data = json.loads(record['raw_json'])
        except Exception:
            pass
    return render_template('briefing.html',
        briefing=briefing_data, record=record,
        history=history, target_date=target_date)


@app.route('/briefing/run', methods=['POST'])
def briefing_run():
    try:
        from mushroom_agent import run_briefing
        _mt.DB_PATH = active_db_path()
        result = run_briefing(triggered_by='manual')
        attn = len(result.get('attention_required', []))
        flash(f"Briefing generated — {attn} attention item{'s' if attn != 1 else ''}.", 'success')
    except Exception as exc:
        flash(f"Briefing failed: {exc}", 'error')
    return redirect(url_for('briefing'))


# ── Scheduler ─────────────────────────────────────────────────────────────────

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    try:
        from mushroom_agent import init_scheduler
        _scheduler = init_scheduler(app)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Could not start briefing scheduler: %s", _e)


# ── Govee CSV Import ──────────────────────────────────────────────────────────

def _parse_govee_csv(conn, content, chamber_id):
    """Parse a Govee H5179 CSV export and insert new rows. Returns (inserted, skipped)."""
    reader = csv.reader(io.StringIO(content))
    ts_col = temp_col = hum_col = None
    use_celsius = False
    headers_found = False

    existing = {r[0] for r in conn.execute(
        "SELECT logged_at FROM environment_logs WHERE chamber_id=?", (chamber_id,)
    ).fetchall()}

    inserted = skipped = 0

    for row in reader:
        if not row or all(c.strip() == '' for c in row):
            continue

        if not headers_found:
            hdrs = [c.strip().lower() for c in row]
            for i, h in enumerate(hdrs):
                if any(k in h for k in ('time', 'date')):
                    ts_col = i
                if 'temp' in h:
                    temp_col = i
                    use_celsius = any(k in h for k in ('°c', '(c)', 'celsius', 'cel'))
                if 'humid' in h:
                    hum_col = i
            if ts_col is None or temp_col is None or hum_col is None:
                raise ValueError(
                    f"Could not find Timestamp, Temperature, and Humidity columns. "
                    f"Headers detected: {row}"
                )
            headers_found = True
            continue

        try:
            ts_raw   = row[ts_col].strip()
            temp_raw = row[temp_col].strip()
            hum_raw  = row[hum_col].strip()
        except IndexError:
            continue

        # Parse timestamp — try common Govee formats
        ts = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%m/%d/%Y %I:%M:%S %p"):
            try:
                ts = datetime.strptime(ts_raw, fmt)
                break
            except ValueError:
                continue
        if ts is None:
            continue

        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        if ts_str in existing:
            skipped += 1
            continue

        try:
            temp_val = float(''.join(c for c in temp_raw if c in '0123456789.-'))
            hum_val  = float(''.join(c for c in hum_raw  if c in '0123456789.-'))
        except ValueError:
            continue

        if use_celsius:
            temp_val = temp_val * 9 / 5 + 32
        temp_val = round(temp_val, 1)
        hum_val  = round(hum_val, 1)

        conn.execute(
            "INSERT INTO environment_logs (chamber_id, logged_at, phase, temp_f, humidity_rh) "
            "VALUES (?, ?, 'fruiting', ?, ?)",
            (chamber_id, ts_str, temp_val, hum_val)
        )
        existing.add(ts_str)
        inserted += 1

    return inserted, skipped


@app.route('/env/import', methods=['GET', 'POST'])
def env_import():
    init_db()
    conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    conn.close()

    if request.method == 'POST':
        chamber_id = request.form.get('chamber_id')
        f = request.files.get('csv_file')
        if not chamber_id:
            flash('Select a chamber.', 'error')
            return redirect(url_for('env_import'))
        if not f or not f.filename:
            flash('No file selected.', 'error')
            return redirect(url_for('env_import'))
        if not f.filename.lower().endswith('.csv'):
            flash('File must be a .csv export from the Govee app.', 'error')
            return redirect(url_for('env_import'))
        try:
            content  = f.stream.read().decode('utf-8-sig')
            conn     = get_db()
            inserted, skipped = _parse_govee_csv(conn, content, int(chamber_id))
            conn.commit()
            conn.close()
            flash(
                f"Import complete: {inserted} row{'s' if inserted != 1 else ''} inserted, "
                f"{skipped} duplicate{'s' if skipped != 1 else ''} skipped.",
                'success'
            )
        except Exception as exc:
            flash(f"Import failed: {exc}", 'error')
        return redirect(url_for('env_history'))

    return render_template('env_import.html', chambers=chambers)


if __name__ == '__main__':
    init_db()
    print("\n  Mushroom Tracker v2 running at http://localhost:5000\n")
    app.run(debug=True, port=5000)
