"""
Mushroom Tracker Web App v2
Run: python mushroom_app.py  →  http://localhost:5000
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3, json, os, csv, io, re
import anthropic as _anthropic
from pathlib import Path
from datetime import datetime, date, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))
import mushroom_tracker as _mt
from roadmap_gates import evaluate_gates
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
        'co2_lo':      v['fruiting_co2_ppm'][0],
        'co2_hi':      v['fruiting_co2_ppm'][1],
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

    harvest_forecast = _build_harvest_forecast(conn)

    conn.close()
    return render_template('dashboard.html',
        chamber=chamber, latest_env=latest_env, batches=batches,
        recent_flushes=recent_flushes, total_yield=total_yield,
        active_count=active_count, env_count=env_count,
        days_running=days_running, avg_be=avg_be,
        harvest_forecast=harvest_forecast)


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


# ── Chamber Suggestion API ────────────────────────────────────────────────────
@app.route('/api/chamber-suggest', methods=['POST'])
def chamber_suggest():
    """Claude AI chamber recommendation: species requirements vs actual chamber readings."""
    try:
        import anthropic as _anthropic
    except ImportError:
        return jsonify({'error': 'anthropic package not installed. Run: pip install anthropic'}), 500

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY environment variable not set'}), 500

    data = request.get_json() or {}
    species = data.get('species', '').strip().lower()
    if not species:
        return jsonify({'error': 'species required'}), 400

    from agent_config import DEFAULT_TIMELINE
    sp_prefs = SPECIES_TIMELINES.get(species, DEFAULT_TIMELINE)
    temp_lo, temp_hi = sp_prefs['fruiting_temp_f']
    hum_lo,  hum_hi  = sp_prefs['fruiting_humidity_rh']

    conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()

    chamber_info = []
    for ch in chambers:
        env = conn.execute("""
            SELECT ROUND(AVG(temp_f),1) avg_temp, ROUND(AVG(humidity_rh),1) avg_hum,
                   COUNT(*) cnt, MAX(logged_at) last_at
            FROM environment_logs
            WHERE chamber_id=? AND logged_at >= datetime('now','-24 hours')
        """, (ch['id'],)).fetchone()

        active = conn.execute("""
            SELECT COUNT(*) cnt,
                   GROUP_CONCAT(label || ' (' || species || ')', ', ') batches
            FROM batches
            WHERE chamber_id=? AND status NOT IN ('done','contaminated','aborted')
        """, (ch['id'],)).fetchone()

        chamber_info.append({
            'id':           ch['id'],
            'name':         ch['name'],
            'type':         ch['chamber_type'] or 'chamber',
            'location':     ch['location'] or '',
            'avg_temp':     env['avg_temp'],
            'avg_hum':      env['avg_hum'],
            'readings_24h': env['cnt'],
            'active_count': active['cnt'],
            'active_list':  active['batches'] or 'none',
        })
    conn.close()

    # Build chamber descriptions for the prompt
    ch_lines = []
    for ch in chamber_info:
        desc = f"Chamber: {ch['name']} ({ch['type']}"
        if ch['location']:
            desc += f", {ch['location']}"
        desc += f")  [id={ch['id']}]"
        if ch['avg_temp'] is not None:
            desc += f"\n  24h avg: {ch['avg_temp']}°F, {ch['avg_hum']}% RH ({ch['readings_24h']} readings)"
        else:
            desc += "\n  24h avg: no recent readings"
        desc += f"\n  Active batches: {ch['active_count']} — {ch['active_list']}"
        ch_lines.append(desc)

    prompt = (
        f"I am starting a new batch of {species.title()}.\n\n"
        f"Species fruiting requirements:\n"
        f"  Temperature: {temp_lo}–{temp_hi}°F\n"
        f"  Humidity: {hum_lo}–{hum_hi}% RH\n\n"
        f"Available chambers:\n" + "\n\n".join(ch_lines) +
        "\n\nRecommend the best chamber for this new batch. "
        "Base your recommendation on how well current actual conditions match species needs "
        "and whether a chamber is already crowded. "
        "If a chamber has no recent readings, note that as uncertainty.\n\n"
        "Return ONLY valid JSON (no markdown fences, no text outside the JSON):\n"
        "{\n"
        '  "recommended_chamber_id": <integer>,\n'
        '  "recommended_chamber_name": "<string>",\n'
        '  "fit_badge": "<Ideal|Good|Marginal|Poor>",\n'
        '  "reasoning": "<2-3 sentences: conditions match, any caveats, crowding>",\n'
        '  "chamber_scores": [\n'
        '    {"chamber_id": <int>, "chamber_name": "<str>", "fit": "<Ideal|Good|Marginal|Poor>", "note": "<one sentence>"}\n'
        '  ]\n'
        "}"
    )

    client = _anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=600,
        system=(
            "You are a mushroom cultivation advisor. "
            "Analyze chamber environmental conditions against species fruiting requirements "
            "and return a structured JSON recommendation. "
            "Return only valid JSON with no surrounding text."
        ),
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = msg.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                return jsonify({'error': 'Could not parse AI response'}), 500
        else:
            return jsonify({'error': 'Could not parse AI response'}), 500

    result['chambers'] = chamber_info
    result['species_range'] = {'temp_lo': temp_lo, 'temp_hi': temp_hi,
                               'hum_lo': hum_lo, 'hum_hi': hum_hi}
    return jsonify(result)


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
    all_substrate_batches = _substrate_batches_with_count(conn)
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
        fruiting_chamber_id = int(f['chamber_id']) if f.get('chamber_id') else chamber['id']
        conn.execute("""INSERT INTO batches
            (chamber_id,colonization_chamber_id,label,species,strain,
             target_temp_f,target_humidity_rh,
             dry_weight_g,moisture_pct,straw_pct,hardwood_pct,bran_pct,gypsum_pct,coco_pct,
             substrate_other,substrate_notes,
             steril_method,steril_temp_f,steril_duration_min,
             inoculation_date,spawn_type,spawn_strain,spawn_rate_pct,spawn_source,spawn_lot,
             colonization_start_date,fruiting_start_date,sourced_block,status,notes,
             substrate_batch_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fruiting_chamber_id,
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
             f.get('status','colonizing'), f.get('notes') or None,
             int(f['substrate_batch_id']) if f.get('substrate_batch_id') else None))
        conn.commit(); conn.close()
        flash(f"Batch '{f['label']}' added.", 'success')
        return redirect(url_for('batches'))

    return render_template('batch_form.html', chamber=chamber, batch=None, all_chambers=all_chambers,
                           all_substrate_batches=all_substrate_batches,
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
    batch_notes = conn.execute(
        "SELECT * FROM batch_notes WHERE batch_id=? ORDER BY created_at ASC", (batch_id,)
    ).fetchall()
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

    ts0 = cs_dt.strftime('%Y-%m-%d %H:%M:%S')
    ts1 = ce_dt.strftime('%Y-%m-%d %H:%M:%S')
    # Temp + humidity: prefer chamber-linked rows, fall back to ambient
    if batch['chamber_id']:
        ch_rows = conn.execute("""
            SELECT logged_at, temp_f, humidity_rh
            FROM environment_logs
            WHERE chamber_id = ? AND logged_at >= ? AND logged_at <= ?
            ORDER BY logged_at ASC
        """, (batch['chamber_id'], ts0, ts1)).fetchall()
    else:
        ch_rows = []
    if not ch_rows:
        ch_rows = conn.execute("""
            SELECT logged_at, temp_f, humidity_rh
            FROM environment_logs
            WHERE chamber_id IS NULL AND batch_id IS NULL
              AND logged_at >= ? AND logged_at <= ?
            ORDER BY logged_at ASC
        """, (ts0, ts1)).fetchall()

    # CO2: ambient sensor only
    co2_rows = conn.execute("""
        SELECT logged_at, co2_ppm
        FROM environment_logs
        WHERE chamber_id IS NULL AND batch_id IS NULL
          AND co2_ppm IS NOT NULL
          AND logged_at >= ? AND logged_at <= ?
        ORDER BY logged_at ASC
    """, (ts0, ts1)).fetchall()

    ch_agg  = _aggregate_env_logs([dict(r) for r in ch_rows],  env_res)
    co2_agg = _aggregate_env_logs([dict(r) for r in co2_rows], env_res)

    batch_chart_data = {
        'labels':      [r['logged_at'][:16] for r in ch_agg],
        'temp':        [r['temp_f']          for r in ch_agg],
        'humidity':    [r['humidity_rh']     for r in ch_agg],
        'co2_labels':  [r['logged_at'][:16] for r in co2_agg],
        'co2':         [r['co2_ppm']         for r in co2_agg],
        'temp_lo':     sp_defaults['temp_lo']     if sp_defaults else None,
        'temp_hi':     sp_defaults['temp_hi']     if sp_defaults else None,
        'humidity_lo': sp_defaults['humidity_lo'] if sp_defaults else None,
        'humidity_hi': sp_defaults['humidity_hi'] if sp_defaults else None,
        'co2_lo':      sp_defaults['co2_lo']      if sp_defaults else None,
        'co2_hi':      sp_defaults['co2_hi']      if sp_defaults else None,
        'fruiting_at': batch['fruiting_start_date'][:10] if batch['fruiting_start_date'] else None,
        'pinning_at':  batch['pinning_started_at'][:10]  if batch['pinning_started_at']  else None,
    }

    conn.close()
    return render_template('batch_detail.html',
        batch=batch, flushes=flushes, sales=sales, yield_chart=yield_chart,
        cycle_days=cycle_days, sp_defaults=sp_defaults, targets_customized=targets_customized,
        batch_chart_data=batch_chart_data, env_res=env_res, resolutions=_ENV_RESOLUTIONS,
        batch_notes=batch_notes)


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


@app.route('/batch/<int:batch_id>/note', methods=['POST'])
def batch_note_add(batch_id):
    body = request.form.get('body', '').strip()
    if body:
        conn = get_db()
        conn.execute("INSERT INTO batch_notes (batch_id, body) VALUES (?, ?)", (batch_id, body))
        conn.commit()
        conn.close()
    return redirect(url_for('batch_detail', batch_id=batch_id) + '#discussion')


@app.route('/batch/<int:batch_id>/note/<int:note_id>/delete', methods=['POST'])
def batch_note_delete(batch_id, note_id):
    conn = get_db()
    conn.execute("DELETE FROM batch_notes WHERE id=? AND batch_id=?", (note_id, batch_id))
    conn.commit()
    conn.close()
    return redirect(url_for('batch_detail', batch_id=batch_id) + '#discussion')


@app.route('/batch/<int:batch_id>/note/<int:note_id>/edit', methods=['POST'])
def batch_note_edit(batch_id, note_id):
    body = request.form.get('body', '').strip()
    if body:
        conn = get_db()
        conn.execute(
            "UPDATE batch_notes SET body=?, updated_at=datetime('now') WHERE id=? AND batch_id=?",
            (body, note_id, batch_id)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('batch_detail', batch_id=batch_id) + '#discussion')


# ── Substrate Batches ─────────────────────────────────────────────────────────

def _substrate_batches_with_count(conn):
    return conn.execute("""
        SELECT sb.*,
               (SELECT COUNT(*) FROM batches WHERE substrate_batch_id=sb.id) AS batch_count
        FROM substrate_batches sb
        ORDER BY sb.date_prepared DESC, sb.id DESC
    """).fetchall()


@app.route('/substrate-batches')
def substrate_batches_list():
    init_db()
    conn = get_db()
    batches = _substrate_batches_with_count(conn)
    unlinked_count = conn.execute(
        "SELECT COUNT(*) FROM batches WHERE substrate_batch_id IS NULL"
    ).fetchone()[0]
    conn.close()
    return render_template('substrate_batches.html', batches=batches, unlinked_count=unlinked_count)


@app.route('/substrate-batches/add', methods=['GET', 'POST'])
def substrate_batch_add():
    init_db()
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        conn.execute("""
            INSERT INTO substrate_batches
                (date_prepared, substrate_type, dry_weight_g, moisture_pct,
                 straw_pct, hardwood_pct, bran_pct, gypsum_pct, coco_pct,
                 substrate_other, steril_method, steril_temp_f, steril_duration_min,
                 cooldown_duration_min, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f.get('date_prepared') or None,
             f.get('substrate_type', '').strip() or None,
             float(f['dry_weight_g']) if f.get('dry_weight_g') else None,
             float(f['moisture_pct']) if f.get('moisture_pct') else None,
             float(f.get('straw_pct') or 0), float(f.get('hardwood_pct') or 0),
             float(f.get('bran_pct') or 0), float(f.get('gypsum_pct') or 0),
             float(f.get('coco_pct') or 0),
             f.get('substrate_other', '').strip() or None,
             f.get('steril_method') or None,
             float(f['steril_temp_f']) if f.get('steril_temp_f') else None,
             int(f['steril_duration_min']) if f.get('steril_duration_min') else None,
             int(f['cooldown_duration_min']) if f.get('cooldown_duration_min') else None,
             f.get('notes', '').strip() or None))
        conn.commit()
        conn.close()
        flash('Substrate batch saved.', 'success')
        return redirect(url_for('substrate_batches_list'))
    return render_template('substrate_batch_form.html', sb=None)


@app.route('/substrate-batches/<int:sb_id>/edit', methods=['GET', 'POST'])
def substrate_batch_edit(sb_id):
    conn = get_db()
    sb = conn.execute("SELECT * FROM substrate_batches WHERE id=?", (sb_id,)).fetchone()
    if not sb:
        conn.close(); flash('Substrate batch not found.', 'error')
        return redirect(url_for('substrate_batches_list'))
    if request.method == 'POST':
        f = request.form
        conn.execute("""
            UPDATE substrate_batches SET
                date_prepared=?, substrate_type=?, dry_weight_g=?, moisture_pct=?,
                straw_pct=?, hardwood_pct=?, bran_pct=?, gypsum_pct=?, coco_pct=?,
                substrate_other=?, steril_method=?, steril_temp_f=?, steril_duration_min=?,
                cooldown_duration_min=?, notes=?
            WHERE id=?""",
            (f.get('date_prepared') or None,
             f.get('substrate_type', '').strip() or None,
             float(f['dry_weight_g']) if f.get('dry_weight_g') else None,
             float(f['moisture_pct']) if f.get('moisture_pct') else None,
             float(f.get('straw_pct') or 0), float(f.get('hardwood_pct') or 0),
             float(f.get('bran_pct') or 0), float(f.get('gypsum_pct') or 0),
             float(f.get('coco_pct') or 0),
             f.get('substrate_other', '').strip() or None,
             f.get('steril_method') or None,
             float(f['steril_temp_f']) if f.get('steril_temp_f') else None,
             int(f['steril_duration_min']) if f.get('steril_duration_min') else None,
             int(f['cooldown_duration_min']) if f.get('cooldown_duration_min') else None,
             f.get('notes', '').strip() or None,
             sb_id))
        conn.commit()
        conn.close()
        flash('Substrate batch updated.', 'success')
        return redirect(url_for('substrate_batches_list'))
    conn.close()
    return render_template('substrate_batch_form.html', sb=sb)


@app.route('/substrate-batches/<int:sb_id>/delete', methods=['POST'])
def substrate_batch_delete(sb_id):
    conn = get_db()
    conn.execute("UPDATE batches SET substrate_batch_id=NULL WHERE substrate_batch_id=?", (sb_id,))
    conn.execute("DELETE FROM substrate_batches WHERE id=?", (sb_id,))
    conn.commit()
    conn.close()
    flash('Substrate batch deleted.', 'success')
    return redirect(url_for('substrate_batches_list'))


@app.route('/api/substrate-batch/<int:sb_id>')
def api_substrate_batch(sb_id):
    conn = get_db()
    sb = conn.execute("SELECT * FROM substrate_batches WHERE id=?", (sb_id,)).fetchone()
    conn.close()
    if not sb:
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'dry_weight_g':        sb['dry_weight_g'],
        'moisture_pct':        sb['moisture_pct'],
        'hardwood_pct':        sb['hardwood_pct'],
        'straw_pct':           sb['straw_pct'],
        'bran_pct':            sb['bran_pct'],
        'gypsum_pct':          sb['gypsum_pct'],
        'coco_pct':            sb['coco_pct'],
        'substrate_other':     sb['substrate_other'],
        'steril_method':       sb['steril_method'],
        'steril_temp_f':       sb['steril_temp_f'],
        'steril_duration_min': sb['steril_duration_min'],
    })


# ── Process Checklists ────────────────────────────────────────────────────────

PROCESS_DEFINITIONS = {
    'substrate_block_prep': {
        'name': 'Substrate Block Prep',
        'description': 'Mix, bag, and sterilize substrate blocks ready for inoculation.',
        'steps': [
            {'key': 'gather_materials',
             'title': 'Gather materials',
             'detail': 'Substrate ingredients (hardwood sawdust, bran, gypsum, etc.), '
                       'spawn bags or containers, scale, mixing tub, pressure cooker or autoclave.'},
            {'key': 'weigh_components',
             'title': 'Weigh dry components',
             'detail': 'Measure each dry ingredient to recipe spec. Note actual weights — '
                       'deviations from recipe affect moisture target.'},
            {'key': 'mix_dry',
             'title': 'Mix dry components',
             'detail': 'Combine all dry ingredients thoroughly before adding water. '
                       'Uneven distribution leads to hot spots during sterilization.'},
            {'key': 'hydrate',
             'title': 'Hydrate to field capacity',
             'detail': 'Add water gradually and mix. Field capacity test: squeeze a handful firmly — '
                       'a few drops should drip, not a stream. Target 60–65% moisture content.'},
            {'key': 'fill_bags',
             'title': 'Fill bags / containers',
             'detail': 'Pack substrate into spawn bags or jars. Target weight per block per your batch plan. '
                       'Leave enough headspace to seal. Wipe bag necks clean.'},
            {'key': 'seal_bags',
             'title': 'Seal bags',
             'detail': 'Fold and tape, apply filter patch, or insert polyfill collar. '
                       'Ensure no gaps that could allow contamination post-sterilization.'},
            {'key': 'load_sterilizer',
             'title': 'Load sterilizer',
             'detail': 'Arrange bags to allow steam or heat penetration between blocks. '
                       'Do not over-pack. Taller bags should stand upright.'},
            {'key': 'sterilize',
             'title': 'Sterilize',
             'detail': 'Pressure cooker: 15 psi / 250 °F for 2.5–3 hrs. '
                       'Autoclave: follow manufacturer cycle. '
                       'Steam pasteurization (straw/oysters): 160–180 °F for 1–2 hrs. '
                       'Start timer once target temp/pressure is reached.'},
            {'key': 'cool_blocks',
             'title': 'Cool to room temperature',
             'detail': 'Move blocks to a clean area and allow to cool fully before inoculating — '
                       'typically 4–12 hours. Do NOT inoculate while blocks are still warm (kills spawn).'},
            {'key': 'inspect',
             'title': 'Inspect bags',
             'detail': 'Check each bag for tears, standing water at the bottom, discoloration, '
                       'or off smells. Flag suspect bags and set aside.'},
            {'key': 'confirm_ready',
             'title': 'Confirm ready for inoculation',
             'detail': 'All blocks are at room temperature, sealed, and visually clear. '
                       'Inoculation area is prepared. Proceed to spawn run.'},
        ],
    },
}


@app.route('/checklist/start', methods=['POST'])
def checklist_start():
    init_db()
    process_type = request.form.get('process_type', 'substrate_block_prep')
    sb_id = request.form.get('substrate_batch_id') or None
    if process_type not in PROCESS_DEFINITIONS:
        flash('Unknown process type.', 'error')
        return redirect(url_for('substrate_batches_list'))
    conn = get_db()
    label = request.form.get('label', '').strip() or None
    if not label and sb_id:
        sb = conn.execute("SELECT date_prepared, substrate_type FROM substrate_batches WHERE id=?",
                          (sb_id,)).fetchone()
        if sb:
            label = f"{sb['substrate_type'] or 'Substrate'} — {sb['date_prepared'] or 'unknown date'}"
    cur = conn.execute(
        "INSERT INTO process_runs (process_type, substrate_batch_id, label) VALUES (?,?,?)",
        (process_type, sb_id, label))
    run_id = cur.lastrowid
    conn.commit(); conn.close()
    return redirect(url_for('checklist_view', run_id=run_id))


@app.route('/checklist/<int:run_id>')
def checklist_view(run_id):
    init_db()
    conn = get_db()
    run = conn.execute("SELECT * FROM process_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close(); flash('Checklist not found.', 'error')
        return redirect(url_for('substrate_batches_list'))
    sb = None
    if run['substrate_batch_id']:
        sb = conn.execute("SELECT * FROM substrate_batches WHERE id=?",
                          (run['substrate_batch_id'],)).fetchone()
    done_keys = {r['step_key'] for r in
                 conn.execute("SELECT step_key FROM process_run_steps WHERE run_id=?",
                              (run_id,)).fetchall()}
    conn.close()
    defn = PROCESS_DEFINITIONS.get(run['process_type'], {})
    steps = defn.get('steps', [])
    total = len(steps)
    completed = sum(1 for s in steps if s['key'] in done_keys)
    return render_template('checklist.html',
                           run=run, sb=sb, defn=defn, steps=steps,
                           done_keys=done_keys, total=total, completed=completed)


@app.route('/checklist/<int:run_id>/step/<step_key>/toggle', methods=['POST'])
def checklist_step_toggle(run_id, step_key):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM process_run_steps WHERE run_id=? AND step_key=?",
        (run_id, step_key)).fetchone()
    if existing:
        conn.execute("DELETE FROM process_run_steps WHERE run_id=? AND step_key=?",
                     (run_id, step_key))
    else:
        conn.execute(
            "INSERT OR IGNORE INTO process_run_steps (run_id, step_key, completed_at) "
            "VALUES (?, ?, datetime('now','localtime'))",
            (run_id, step_key))
    conn.commit(); conn.close()
    return redirect(url_for('checklist_view', run_id=run_id))


@app.route('/checklist/<int:run_id>/finish', methods=['POST'])
def checklist_finish(run_id):
    conn = get_db()
    notes = request.form.get('notes', '').strip() or None
    conn.execute(
        "UPDATE process_runs SET completed_at=datetime('now','localtime'), notes=? WHERE id=?",
        (notes, run_id))
    conn.commit(); conn.close()
    flash('Checklist completed and saved.', 'success')
    return redirect(url_for('checklist_view', run_id=run_id))


@app.route('/checklists')
def checklists_list():
    init_db()
    conn = get_db()
    runs = conn.execute("""
        SELECT pr.*, sb.date_prepared, sb.substrate_type,
               COUNT(prs.id) AS steps_done
        FROM process_runs pr
        LEFT JOIN substrate_batches sb ON sb.id = pr.substrate_batch_id
        LEFT JOIN process_run_steps prs ON prs.run_id = pr.id
        GROUP BY pr.id
        ORDER BY pr.started_at DESC
    """).fetchall()
    conn.close()
    return render_template('checklists.html', runs=runs,
                           process_defs=PROCESS_DEFINITIONS)


# ── Grain Jars ────────────────────────────────────────────────────────────────

def _grain_jars_with_refs(conn):
    return conn.execute("""
        SELECT gj.*,
               ll.vendor      AS lot_vendor,
               ll.species     AS lot_species,
               ll.lot_number  AS lot_lot_number,
               sb.date_prepared AS sb_date,
               sb.substrate_type AS sb_type
        FROM grain_jars gj
        LEFT JOIN lc_lots ll ON gj.lc_lot_id = ll.id
        LEFT JOIN substrate_batches sb ON gj.used_in_substrate_batch_id = sb.id
        ORDER BY gj.inoculation_date DESC, gj.id DESC
    """).fetchall()


@app.route('/grain-jars')
def grain_jars_list():
    init_db()
    conn = get_db()
    jars = _grain_jars_with_refs(conn)
    lc_lots = conn.execute("SELECT * FROM lc_lots ORDER BY order_date DESC").fetchall()
    substrate_batches = conn.execute(
        "SELECT * FROM substrate_batches ORDER BY date_prepared DESC"
    ).fetchall()
    conn.close()
    return render_template('grain_jars.html', jars=jars,
                           lc_lots=lc_lots, substrate_batches=substrate_batches)


@app.route('/grain-jars/add', methods=['GET', 'POST'])
def grain_jar_add():
    init_db()
    conn = get_db()
    lc_lots = conn.execute("SELECT * FROM lc_lots ORDER BY order_date DESC").fetchall()
    substrate_batches = conn.execute(
        "SELECT * FROM substrate_batches ORDER BY date_prepared DESC"
    ).fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute("""
            INSERT INTO grain_jars
                (lc_lot_id, spawn_source, species, inoculation_date,
                 full_colonization_date, outcome, used_in_substrate_batch_id, notes)
            VALUES (?,?,?,?,?,?,?,?)""",
            (int(f['lc_lot_id']) if f.get('lc_lot_id') else None,
             f.get('spawn_source', '').strip() or None,
             f['species'].strip(),
             f.get('inoculation_date') or None,
             f.get('full_colonization_date') or None,
             f.get('outcome') or None,
             int(f['used_in_substrate_batch_id']) if f.get('used_in_substrate_batch_id') else None,
             f.get('notes', '').strip() or None))
        conn.commit()
        conn.close()
        flash('Grain jar logged.', 'success')
        return redirect(url_for('grain_jars_list'))
    conn.close()
    return render_template('grain_jar_form.html', jar=None,
                           lc_lots=lc_lots, substrate_batches=substrate_batches)


@app.route('/grain-jars/<int:jar_id>/edit', methods=['GET', 'POST'])
def grain_jar_edit(jar_id):
    conn = get_db()
    jar = conn.execute("SELECT * FROM grain_jars WHERE id=?", (jar_id,)).fetchone()
    if not jar:
        conn.close(); flash('Grain jar not found.', 'error')
        return redirect(url_for('grain_jars_list'))
    lc_lots = conn.execute("SELECT * FROM lc_lots ORDER BY order_date DESC").fetchall()
    substrate_batches = conn.execute(
        "SELECT * FROM substrate_batches ORDER BY date_prepared DESC"
    ).fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute("""
            UPDATE grain_jars SET
                lc_lot_id=?, spawn_source=?, species=?, inoculation_date=?,
                full_colonization_date=?, outcome=?, used_in_substrate_batch_id=?, notes=?
            WHERE id=?""",
            (int(f['lc_lot_id']) if f.get('lc_lot_id') else None,
             f.get('spawn_source', '').strip() or None,
             f['species'].strip(),
             f.get('inoculation_date') or None,
             f.get('full_colonization_date') or None,
             f.get('outcome') or None,
             int(f['used_in_substrate_batch_id']) if f.get('used_in_substrate_batch_id') else None,
             f.get('notes', '').strip() or None,
             jar_id))
        conn.commit()
        conn.close()
        flash('Grain jar updated.', 'success')
        return redirect(url_for('grain_jars_list'))
    conn.close()
    return render_template('grain_jar_form.html', jar=jar,
                           lc_lots=lc_lots, substrate_batches=substrate_batches)


@app.route('/grain-jars/<int:jar_id>/delete', methods=['POST'])
def grain_jar_delete(jar_id):
    conn = get_db()
    conn.execute("DELETE FROM grain_jars WHERE id=?", (jar_id,))
    conn.commit()
    conn.close()
    flash('Grain jar deleted.', 'success')
    return redirect(url_for('grain_jars_list'))


# ── LC Lots ───────────────────────────────────────────────────────────────────

@app.route('/lc-lots')
def lc_lots_list():
    init_db()
    conn = get_db()
    lots = conn.execute("SELECT * FROM lc_lots ORDER BY order_date DESC, id DESC").fetchall()
    conn.close()
    return render_template('lc_lots.html', lots=lots)


@app.route('/lc-lots/add', methods=['GET', 'POST'])
def lc_lot_add():
    init_db()
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        conn.execute(
            "INSERT INTO lc_lots (vendor, species, order_date, lot_number, media_type, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (f['vendor'].strip(),
             f['species'].strip(),
             f.get('order_date') or None,
             f.get('lot_number', '').strip() or None,
             f.get('media_type', '').strip() or None,
             f.get('notes', '').strip() or None))
        conn.commit()
        conn.close()
        flash(f"LC lot from '{f['vendor'].strip()}' added.", 'success')
        return redirect(url_for('lc_lots_list'))
    return render_template('lc_lot_form.html', lot=None)


@app.route('/lc-lots/<int:lot_id>/edit', methods=['GET', 'POST'])
def lc_lot_edit(lot_id):
    conn = get_db()
    lot = conn.execute("SELECT * FROM lc_lots WHERE id=?", (lot_id,)).fetchone()
    if not lot:
        conn.close(); flash('LC lot not found.', 'error')
        return redirect(url_for('lc_lots_list'))
    if request.method == 'POST':
        f = request.form
        conn.execute(
            "UPDATE lc_lots SET vendor=?, species=?, order_date=?, lot_number=?, media_type=?, notes=? WHERE id=?",
            (f['vendor'].strip(),
             f['species'].strip(),
             f.get('order_date') or None,
             f.get('lot_number', '').strip() or None,
             f.get('media_type', '').strip() or None,
             f.get('notes', '').strip() or None,
             lot_id))
        conn.commit()
        conn.close()
        flash('LC lot updated.', 'success')
        return redirect(url_for('lc_lots_list'))
    conn.close()
    return render_template('lc_lot_form.html', lot=lot)


@app.route('/lc-lots/<int:lot_id>/delete', methods=['POST'])
def lc_lot_delete(lot_id):
    conn = get_db()
    lot = conn.execute("SELECT vendor, species FROM lc_lots WHERE id=?", (lot_id,)).fetchone()
    if lot:
        conn.execute("DELETE FROM lc_lots WHERE id=?", (lot_id,))
        conn.commit()
        flash(f"LC lot deleted.", 'success')
    conn.close()
    return redirect(url_for('lc_lots_list'))


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
                           default_pinning_date=default_pinning_date, flush=None)


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
        if row.get('temp_f')      is not None: buckets[key]['temp'].append(row['temp_f'])
        if row.get('humidity_rh') is not None: buckets[key]['hum'].append(row['humidity_rh'])
        if row.get('co2_ppm')     is not None: buckets[key]['co2'].append(row['co2_ppm'])
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


def _build_harvest_forecast(conn):
    """
    Project harvest windows for all active batches using SPECIES_TIMELINES midpoints.
    Returns list of dicts sorted by projected_mid date.
    """
    from agent_config import DEFAULT_TIMELINE

    batches = conn.execute("""
        SELECT b.*,
               (SELECT MAX(harvest_date) FROM flushes WHERE batch_id = b.id) AS last_harvest_date
        FROM batches b
        WHERE b.status IN ('colonizing','colonized','pinning','fruiting','resting')
        ORDER BY b.id
    """).fetchall()

    today = date.today()
    forecast = []

    for b in batches:
        sp_key = (b['species'] or '').lower()
        tl = SPECIES_TIMELINES.get(sp_key, DEFAULT_TIMELINE)

        col_lo, col_hi = tl['colonization_days']
        pin_lo, pin_hi = tl['days_to_pin']
        har_lo, har_hi = tl['days_to_harvest']
        col_mid = (col_lo + col_hi) / 2
        pin_mid = (pin_lo + pin_hi) / 2
        har_mid = (har_lo + har_hi) / 2

        status = b['status']
        proj_mid = proj_lo = proj_hi = None
        confidence = 'Low'
        note = None

        try:
            if status == 'colonizing' and b['inoculation_date']:
                base = date.fromisoformat(b['inoculation_date'][:10])
                proj_mid = base + timedelta(days=round(col_mid + pin_mid + har_mid))
                proj_lo  = base + timedelta(days=col_lo + pin_lo + har_lo)
                proj_hi  = base + timedelta(days=col_hi + pin_hi + har_hi)
                confidence = 'Low'
                note = 'Est. colonization + pin + harvest'

            elif status == 'colonized':
                col_end = b['colonization_end_date'] or b['inoculation_date']
                if not col_end:
                    continue
                base = date.fromisoformat(col_end[:10])
                if b['colonization_end_date']:
                    base = date.fromisoformat(b['colonization_end_date'][:10])
                else:
                    base = date.fromisoformat(b['inoculation_date'][:10]) + timedelta(days=round(col_mid))
                proj_mid = base + timedelta(days=round(pin_mid + har_mid))
                proj_lo  = base + timedelta(days=pin_lo + har_lo)
                proj_hi  = base + timedelta(days=pin_hi + har_hi)
                confidence = 'Medium'
                note = 'Colonized — waiting on pins'

            elif status == 'pinning':
                pin_start = b['pinning_started_at'] or str(today)
                base = date.fromisoformat(pin_start[:10])
                proj_mid = base + timedelta(days=round(har_mid))
                proj_lo  = base + timedelta(days=har_lo)
                proj_hi  = base + timedelta(days=har_hi)
                confidence = 'High'
                note = 'Pinning — harvest window close'

            elif status == 'fruiting':
                proj_mid = today
                proj_lo  = today
                proj_hi  = today + timedelta(days=har_hi)
                confidence = 'Imminent'
                note = 'Fruiting now'

            elif status == 'resting' and b['last_harvest_date']:
                base = date.fromisoformat(b['last_harvest_date'][:10]) + timedelta(days=7)
                proj_mid = base + timedelta(days=round(pin_mid + har_mid))
                proj_lo  = base + timedelta(days=pin_lo + har_lo)
                proj_hi  = base + timedelta(days=pin_hi + har_hi)
                confidence = 'Medium'
                note = 'Next flush after rest'

            else:
                continue

        except (ValueError, TypeError):
            continue

        days_out = (proj_mid - today).days

        def _fmt(d):
            return d.strftime('%b ') + str(d.day)

        if proj_lo.month == proj_hi.month:
            display_range = f"{_fmt(proj_lo)}–{proj_hi.day}"
        else:
            display_range = f"{_fmt(proj_lo)} – {_fmt(proj_hi)}"

        forecast.append({
            'batch_id':      b['id'],
            'label':         b['label'],
            'species':       b['species'],
            'status':        status,
            'proj_mid':      proj_mid,
            'display_mid':   _fmt(proj_mid),
            'display_range': display_range,
            'confidence':    confidence,
            'days_out':      days_out,
            'note':          note,
        })

    forecast.sort(key=lambda x: x['proj_mid'])
    return forecast


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


# ── Chamber management ────────────────────────────────────────────────────────

@app.route('/chambers')
def chambers_list():
    conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    batch_counts = {r[0]: r[1] for r in conn.execute(
        "SELECT chamber_id, COUNT(*) FROM batches WHERE status NOT IN ('retired','done') "
        "AND chamber_id IS NOT NULL GROUP BY chamber_id"
    ).fetchall()}
    conn.close()
    return render_template('chambers_list.html', chambers=chambers,
                           batch_counts=batch_counts, chamber_types=CHAMBER_TYPES)


@app.route('/chambers/new', methods=['GET', 'POST'])
def chamber_add():
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        conn.execute(
            "INSERT INTO chambers(name,location,chamber_type,target_temp_f,target_humidity_rh,notes) "
            "VALUES(?,?,?,?,?,?)",
            (f.get('name') or 'Chamber',
             f.get('location') or None,
             f.get('chamber_type') or None,
             float(f.get('target_temp') or 72),
             float(f.get('target_humidity') or 90),
             f.get('notes') or None))
        conn.commit(); conn.close()
        flash('Chamber added.', 'success')
        return redirect(url_for('chambers_list'))
    return render_template('chamber_form.html', chamber=None, chamber_types=CHAMBER_TYPES)


@app.route('/chambers/<int:chamber_id>/edit', methods=['GET', 'POST'])
def chamber_edit(chamber_id):
    conn = get_db()
    chamber = conn.execute("SELECT * FROM chambers WHERE id=?", (chamber_id,)).fetchone()
    if not chamber:
        conn.close(); flash('Chamber not found.', 'error')
        return redirect(url_for('chambers_list'))
    if request.method == 'POST':
        f = request.form
        conn.execute(
            "UPDATE chambers SET name=?,location=?,chamber_type=?,target_temp_f=?,target_humidity_rh=?,notes=? WHERE id=?",
            (f.get('name') or chamber['name'],
             f.get('location') or None,
             f.get('chamber_type') or None,
             float(f.get('target_temp') or 72),
             float(f.get('target_humidity') or 90),
             f.get('notes') or None,
             chamber_id))
        conn.commit(); conn.close()
        flash('Chamber updated.', 'success')
        return redirect(url_for('chambers_list'))
    conn.close()
    return render_template('chamber_form.html', chamber=chamber, chamber_types=CHAMBER_TYPES)


# Legacy redirect so old /setup/edit bookmarks still work
@app.route('/setup/edit')
def chamber_edit_legacy():
    ch = get_primary_chamber()
    if ch:
        return redirect(url_for('chamber_edit', chamber_id=ch['id']))
    return redirect(url_for('setup'))


@app.route('/batch/<int:batch_id>/edit', methods=['GET','POST'])
def batch_edit(batch_id):
    conn = get_db()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        conn.close(); flash('Batch not found.','error')
        return redirect(url_for('batches'))
    chamber = get_primary_chamber()
    all_chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    all_substrate_batches = _substrate_batches_with_count(conn)
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
        edit_chamber_id = int(f['chamber_id']) if f.get('chamber_id') else batch['chamber_id']
        conn.execute("""UPDATE batches SET
            chamber_id=?,label=?,species=?,strain=?,
            colonization_chamber_id=?,
            target_temp_f=?,target_humidity_rh=?,
            dry_weight_g=?,moisture_pct=?,straw_pct=?,hardwood_pct=?,bran_pct=?,
            gypsum_pct=?,coco_pct=?,substrate_other=?,substrate_notes=?,
            steril_method=?,steril_temp_f=?,steril_duration_min=?,
            inoculation_date=?,spawn_type=?,spawn_strain=?,spawn_rate_pct=?,
            spawn_source=?,spawn_lot=?,fruiting_start_date=?,sourced_block=?,notes=?,
            substrate_batch_id=?
            WHERE id=?""",
            (edit_chamber_id,
             f['label'], species, f.get('strain') or None,
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
             f.get('notes') or None,
             int(f['substrate_batch_id']) if f.get('substrate_batch_id') else None,
             batch_id))
        conn.commit(); conn.close()
        flash(f"Batch '{f['label']}' updated.", 'success')
        return redirect(url_for('batch_detail', batch_id=batch_id))
    conn.close()
    return render_template('batch_form.html', chamber=chamber, batch=batch, all_chambers=all_chambers,
                           all_substrate_batches=all_substrate_batches,
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
    roadmap_data = None
    try:
        _gate_res = evaluate_gates(db_path=active_db_path())
        _rconn = get_db()
        _ms_rows = _rconn.execute(
            "SELECT * FROM roadmap_milestones ORDER BY target_date, id"
        ).fetchall()
        _rconn.close()
        _today = date.today()
        _milestones = []
        for _r in _ms_rows:
            _m = dict(_r)
            _m['display_status'], _m['gate_result'] = _roadmap_display_status(
                _m, _gate_res, _today)
            _milestones.append(_m)
        roadmap_data = {
            'milestones':     _milestones,
            'gate_results':   _gate_res,
            'days_to_market': (date(2027, 5, 24) - _today).days,
        }
    except Exception:
        pass

    return render_template('briefing.html',
        briefing=briefing_data, record=record,
        history=history, target_date=target_date,
        roadmap_data=roadmap_data)


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
    ts_col = temp_col = hum_col = co2_col = None
    use_celsius = False
    headers_found = False

    if chamber_id is not None:
        existing = {r[0] for r in conn.execute(
            "SELECT logged_at FROM environment_logs WHERE chamber_id=?", (chamber_id,)
        ).fetchall()}
    else:
        existing = {r[0] for r in conn.execute(
            "SELECT logged_at FROM environment_logs WHERE chamber_id IS NULL"
        ).fetchall()}

    inserted = skipped = updated = 0

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
                if any(k in h for k in ('co2', 'co₂', 'carbon')):
                    co2_col = i
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
            # Backfill CO2 into an existing ambient row that has no CO2 yet
            if co2_col is not None and chamber_id is None:
                try:
                    co2_raw = row[co2_col].strip()
                    co2_val = round(float(''.join(c for c in co2_raw if c in '0123456789.-')))
                    conn.execute(
                        "UPDATE environment_logs SET co2_ppm=? "
                        "WHERE chamber_id IS NULL AND batch_id IS NULL "
                        "AND logged_at=? AND co2_ppm IS NULL",
                        (co2_val, ts_str)
                    )
                    updated += 1
                except (ValueError, IndexError):
                    skipped += 1
            else:
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

        co2_val = None
        if co2_col is not None:
            try:
                co2_raw = row[co2_col].strip()
                co2_val = round(float(''.join(c for c in co2_raw if c in '0123456789.-')))
            except (ValueError, IndexError):
                pass

        conn.execute(
            "INSERT INTO environment_logs (chamber_id, logged_at, phase, temp_f, humidity_rh, co2_ppm) "
            "VALUES (?, ?, 'fruiting', ?, ?, ?)",
            (chamber_id, ts_str, temp_val, hum_val, co2_val)
        )
        existing.add(ts_str)
        inserted += 1

    return inserted, updated, skipped


@app.route('/env/import', methods=['GET', 'POST'])
def env_import():
    init_db()
    conn = get_db()
    chambers = conn.execute("SELECT * FROM chambers ORDER BY id").fetchall()
    conn.close()

    if request.method == 'POST':
        raw_id     = request.form.get('chamber_id')
        chamber_id = int(raw_id) if raw_id else None
        f = request.files.get('csv_file')
        if not f or not f.filename:
            flash('No file selected.', 'error')
            return redirect(url_for('env_import'))
        if not f.filename.lower().endswith('.csv'):
            flash('File must be a .csv export from the Govee app.', 'error')
            return redirect(url_for('env_import'))
        try:
            content  = f.stream.read().decode('utf-8-sig')
            conn     = get_db()
            inserted, updated, skipped = _parse_govee_csv(conn, content, chamber_id)
            conn.commit()
            conn.close()
            parts = []
            if inserted:
                parts.append(f"{inserted} row{'s' if inserted != 1 else ''} inserted")
            if updated:
                parts.append(f"{updated} row{'s' if updated != 1 else ''} updated with CO2")
            if skipped:
                parts.append(f"{skipped} duplicate{'s' if skipped != 1 else ''} skipped")
            flash(f"Import complete: {', '.join(parts) or 'nothing to import'}.", 'success')
        except Exception as exc:
            flash(f"Import failed: {exc}", 'error')
        return redirect(url_for('env_history'))

    return render_template('env_import.html', chambers=chambers)


# ── Roadmap ───────────────────────────────────────────────────────────────────

def _roadmap_display_status(m: dict, gate_results: dict, today: date) -> tuple:
    """Return (display_status, gate_result) for one milestone row."""
    if m['gate_type'] == 'auto' and m['gate_key']:
        gate = gate_results.get(m['gate_key'], {})
        gs = gate.get('status', 'pending')
        try:
            target = date.fromisoformat(m['target_date'])
        except Exception:
            target = today
        if gs == 'complete':
            return 'complete', gate
        elif gs == 'on_track':
            return ('on_track' if target >= today else 'at_risk'), gate
        else:
            days_out = (target - today).days
            return ('at_risk' if days_out <= 30 else 'pending'), gate
    return m['status'], None


@app.route('/roadmap')
def roadmap():
    init_db()
    conn = get_db()
    milestones = conn.execute(
        "SELECT * FROM roadmap_milestones ORDER BY target_date, id"
    ).fetchall()
    conn.close()

    try:
        gate_results = evaluate_gates(db_path=active_db_path())
    except Exception:
        gate_results = {}

    today = date.today()
    phases: dict = {}

    for row in milestones:
        m = dict(row)
        m['display_status'], m['gate_result'] = _roadmap_display_status(m, gate_results, today)
        ph = m['phase']
        if ph not in phases:
            phases[ph] = {'label': m['phase_label'], 'milestones': []}
        phases[ph]['milestones'].append(m)

    phases = dict(sorted(phases.items()))
    all_ms = [m for ph in phases.values() for m in ph['milestones']]
    total          = len(all_ms)
    complete_count = sum(1 for m in all_ms if m['display_status'] == 'complete')
    at_risk_count  = sum(1 for m in all_ms if m['display_status'] == 'at_risk')
    days_to_market = (date(2027, 5, 24) - today).days

    return render_template('roadmap.html',
        phases=phases, today=str(today),
        total=total, complete_count=complete_count,
        at_risk_count=at_risk_count, days_to_market=days_to_market,
        gate_results=gate_results)


@app.route('/roadmap/milestone/<int:mid>/complete', methods=['POST'])
def roadmap_milestone_complete(mid):
    conn = get_db()
    m = conn.execute("SELECT status, gate_type FROM roadmap_milestones WHERE id=?", (mid,)).fetchone()
    if m and m['gate_type'] == 'manual':
        if m['status'] == 'complete':
            conn.execute(
                "UPDATE roadmap_milestones SET status='pending', completed_at=NULL WHERE id=?",
                (mid,))
        else:
            conn.execute(
                "UPDATE roadmap_milestones SET status='complete', completed_at=? WHERE id=?",
                (str(date.today()), mid))
        conn.commit()
    conn.close()
    return redirect(url_for('roadmap'))


@app.route('/roadmap/milestone/<int:mid>/note', methods=['POST'])
def roadmap_milestone_note(mid):
    note = request.form.get('notes', '').strip() or None
    conn = get_db()
    conn.execute("UPDATE roadmap_milestones SET notes=? WHERE id=?", (note, mid))
    conn.commit()
    conn.close()
    return redirect(url_for('roadmap'))


# ── Interactive Q&A ───────────────────────────────────────────────────────────

_ASK_SYSTEM = (
    "You are a mushroom cultivation data analyst for a small farm operation. "
    "Use run_sql to query the SQLite database and answer questions about batches, "
    "harvests, yields, contamination rates, environmental conditions, and performance. "
    "Always query before answering — never guess at data. "
    "Keep answers concise and conversational. "
    "Never run UPDATE, INSERT, DELETE, DROP, or any write operation."
)

_ASK_TOOLS = [
    {
        "name": "run_sql",
        "description": "Execute a read-only SQL SELECT query against the mushroom tracker database.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A SQL SELECT statement"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_schema",
        "description": "Get the database schema — table names and column definitions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _ask_schema_text():
    conn = get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    parts = []
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t['name']})").fetchall()
        col_str = ', '.join(f"{c['name']} {c['type']}" for c in cols)
        parts.append(f"{t['name']}({col_str})")
    conn.close()
    return '\n'.join(parts)


@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    context  = data.get('context') or {}
    history  = data.get('history') or []  # [{role, content}, ...] plain-text pairs

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    try:
        client = _anthropic.Anthropic()
    except Exception:
        return jsonify({'error': 'AI client unavailable — check ANTHROPIC_API_KEY'}), 503

    # Prepend batch context to the question when present
    user_content = question
    if context.get('batch_id'):
        user_content = f"[Context: viewing batch #{context['batch_id']}]\n\n{question}"

    # Cap history to 10 messages (5 exchange pairs) to stay within token budget
    trimmed = history[-10:] if len(history) > 10 else history
    messages = [{'role': h['role'], 'content': h['content']} for h in trimmed]
    messages.append({'role': 'user', 'content': user_content})

    queries_run = []
    last_resp   = None

    try:
        for _ in range(5):
            resp = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=1024,
                system=_ASK_SYSTEM,
                tools=_ASK_TOOLS,
                messages=messages,
            )
            last_resp = resp
            messages.append({'role': 'assistant', 'content': resp.content})

            if resp.stop_reason in ('end_turn', None):
                break
            if resp.stop_reason != 'tool_use':
                break

            tool_results = []
            for block in resp.content:
                if block.type != 'tool_use':
                    continue
                if block.name == 'get_schema':
                    result = _ask_schema_text()
                elif block.name == 'run_sql':
                    q = (block.input.get('query') or '').strip()
                    if not re.match(r'^\s*(SELECT|WITH)\b', q, re.IGNORECASE):
                        result = 'ERROR: Only SELECT/WITH queries are permitted.'
                    else:
                        try:
                            conn = get_db()
                            rows = conn.execute(q).fetchmany(200)
                            conn.close()
                            if rows:
                                cols = list(rows[0].keys())
                                lines = ['\t'.join(cols)]
                                lines += ['\t'.join('' if rows[i][c] is None else str(rows[i][c]) for c in cols)
                                          for i in range(len(rows))]
                                result = '\n'.join(lines)
                            else:
                                result = '(no rows)'
                            queries_run.append(q)
                        except Exception as e:
                            result = f'ERROR: {e}'
                else:
                    result = 'Unknown tool.'
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': result,
                })
            messages.append({'role': 'user', 'content': tool_results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if last_resp is None:
        return jsonify({'answer': 'No response generated.', 'queries_run': []}), 200

    answer = ' '.join(
        b.text for b in last_resp.content if hasattr(b, 'text')
    ).strip() or "I wasn't able to answer that question."

    return jsonify({'answer': answer, 'queries_run': queries_run})


if __name__ == '__main__':
    init_db()
    print("\n  Mushroom Tracker v2 running at http://localhost:5000\n")
    app.run(host='0.0.0.0', port=5000)
