#!/usr/bin/env python3
"""ReefPilot — AI-powered saltwater reef tank management app."""

import os
import json
import uuid
import hashlib
import random
import time
from datetime import datetime, timedelta, date
from functools import wraps
from collections import defaultdict

import bcrypt

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory, send_file, session
from werkzeug.utils import secure_filename

from reef_db import get_db, db_execute, db_fetchall, db_fetchone, db_fetchval, init_db, USE_POSTGRES
from reef_data import SALT_BRANDS, PARAMETER_TYPES, PARAMETER_RANGES, TANK_TYPES, DOSING_PRICES, FOOD_PRICES, REEF_LIGHTS
from reef_costs import calculate_all_costs
from reef_ai import (build_system_prompt, extract_params_from_response, clean_response,
                      chat_with_ai, format_ranges_for_prompt, ONBOARDING_PLAN_PROMPT,
                      MAINTENANCE_PLAN_PROMPT)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'reefpilot-dev-key-change-in-prod')

# Custom JSON encoder to handle Postgres date/datetime objects
from flask.json.provider import DefaultJSONProvider
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, timedelta):
            return str(o)
        return super().default(o)
app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)

REEF_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'reef')
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'tank_photos')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Auth helpers ────────────────────────────────────────────────────────────

def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, hashed):
    """Check a password against a hash. Supports both bcrypt and legacy SHA-256."""
    if hashed.startswith('$2b$') or hashed.startswith('$2a$'):
        return bcrypt.checkpw(password.encode(), hashed.encode())
    # Legacy SHA-256 fallback for existing accounts
    return hashlib.sha256(password.encode()).hexdigest() == hashed


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'reef_user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Rate Limiter (in-memory, per-IP) ───────────────────────────────────────

_rate_buckets = defaultdict(list)

def rate_limit(key_prefix, max_requests=5, window_seconds=300):
    """Simple in-memory rate limiter. Returns (allowed, retry_after)."""
    ip = request.remote_addr or 'unknown'
    key = f"{key_prefix}:{ip}"
    now = time.time()
    # Prune old entries
    _rate_buckets[key] = [t for t in _rate_buckets[key] if t > now - window_seconds]
    if len(_rate_buckets[key]) >= max_requests:
        retry_after = int(window_seconds - (now - _rate_buckets[key][0]))
        return False, retry_after
    _rate_buckets[key].append(now)
    return True, 0


# ── Date helpers ──────────────────────────────────────────────────────────

def to_date(val):
    """Convert a value to a date object. Postgres returns date objects, SQLite returns strings."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val))


def to_date_str(val):
    """Convert a value to an ISO date string."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if isinstance(val, (date, datetime)):
        return val.isoformat() if isinstance(val, date) else val.date().isoformat()
    return str(val)


# ── Email helpers ──────────────────────────────────────────────────────────

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

def generate_code():
    """Generate a 6-digit verification code."""
    return str(random.randint(100000, 999999))


def send_email(to, subject, html_body):
    """Send email via Resend HTTP API using http.client. Returns True on success."""
    api_key = os.environ.get('RESEND_API_KEY', '')
    if not api_key:
        print(f"[DEV EMAIL] To: {to}, Subject: {subject}")
        print(f"[DEV EMAIL] Body: {html_body}")
        return True
    try:
        import http.client
        from_email = os.environ.get('FROM_EMAIL', 'ReefPilot <onboarding@resend.dev>')
        payload = json.dumps({
            'from': from_email,
            'to': [to],
            'subject': subject,
            'html': html_body,
        })
        conn = http.client.HTTPSConnection('api.resend.com', timeout=10)
        conn.request('POST', '/emails', body=payload, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'ReefPilot/1.0',
        })
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        if resp.status == 200:
            print(f"Email sent to {to}: {body}")
            return True
        else:
            print(f"Email send error: {resp.status} {resp.reason} — {body}")
            return False
    except Exception as e:
        print(f"Email send error: {e}")
        return False


def store_code(conn, email, code, code_type, expires_minutes=15):
    """Store a verification/reset code in the database."""
    # Invalidate previous unused codes of same type
    db_execute(conn, 'UPDATE auth_codes SET used = 1 WHERE email = ? AND code_type = ? AND used = 0',
               [email, code_type])
    expires_at = (datetime.utcnow() + timedelta(minutes=expires_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    db_execute(conn, '''
        INSERT INTO auth_codes (email, code, code_type, expires_at)
        VALUES (?, ?, ?, ?)
    ''', [email, code, code_type, expires_at])
    conn.commit()


def verify_code(conn, email, code, code_type):
    """Verify a code. Returns True if valid, False otherwise."""
    row = db_fetchone(conn, '''
        SELECT id, code, expires_at, attempts FROM auth_codes
        WHERE email = ? AND code_type = ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', [email, code_type])
    if not row:
        return False
    # Max 5 attempts per code
    if row['attempts'] >= 5:
        db_execute(conn, 'UPDATE auth_codes SET used = 1 WHERE id = ?', [row['id']])
        conn.commit()
        return False
    # Check expiry
    expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S') if isinstance(row['expires_at'], str) else row['expires_at']
    if datetime.utcnow() > expires:
        db_execute(conn, 'UPDATE auth_codes SET used = 1 WHERE id = ?', [row['id']])
        conn.commit()
        return False
    # Check code match
    if row['code'] != code:
        db_execute(conn, 'UPDATE auth_codes SET attempts = attempts + 1 WHERE id = ?', [row['id']])
        conn.commit()
        return False
    # Mark used
    db_execute(conn, 'UPDATE auth_codes SET used = 1 WHERE id = ?', [row['id']])
    conn.commit()
    return True


def validate_password(password):
    """Validate password complexity. Returns error message or None."""
    if len(password) < 8:
        return 'Password must be at least 8 characters'
    if not any(c.isupper() for c in password):
        return 'Password must contain an uppercase letter'
    if not any(c.islower() for c in password):
        return 'Password must contain a lowercase letter'
    if not any(c.isdigit() for c in password):
        return 'Password must contain a number'
    return None


# ── Static routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(REEF_STATIC, 'index.html')


@app.route('/reef')
@app.route('/reef/')
def reef_index():
    return send_from_directory(REEF_STATIC, 'index.html')


@app.route('/manifest.json')
def manifest():
    return send_from_directory(REEF_STATIC, 'manifest.json')


@app.route('/sw.js')
def service_worker():
    resp = send_from_directory(REEF_STATIC, 'sw.js', mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/privacy')
@app.route('/privacy-policy')
def privacy_policy():
    return send_from_directory(REEF_STATIC, 'privacy-policy.html')


@app.route('/terms')
@app.route('/terms-of-service')
def terms_of_service():
    return send_from_directory(REEF_STATIC, 'terms-of-service.html')


# ── Auth endpoints ──────────────────────────────────────────────────────────

@app.route('/reef/api/auth/register', methods=['POST'])
def register():
    allowed, retry_after = rate_limit('register', max_requests=5, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many attempts. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    display_name = (data.get('display_name') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    pw_error = validate_password(password)
    if pw_error:
        return jsonify({'error': pw_error}), 400

    conn = get_db()
    try:
        existing = db_fetchone(conn, 'SELECT id FROM reef_users WHERE email = ?', [email])
        if existing:
            return jsonify({'error': 'Email already registered'}), 409

        db_execute(conn, '''
            INSERT INTO reef_users (email, password_hash, display_name, email_verified)
            VALUES (?, ?, ?, 0)
        ''', [email, hash_password(password), display_name or email.split('@')[0]])
        conn.commit()

        # Send verification email
        code = generate_code()
        store_code(conn, email, code, 'verify')
        send_email(email, 'ReefPilot — Verify Your Email',
                   f'<h2>Welcome to ReefPilot!</h2><p>Your verification code is:</p>'
                   f'<h1 style="letter-spacing:8px;font-family:monospace">{code}</h1>'
                   f'<p>This code expires in 15 minutes.</p>')

        return jsonify({'needs_verification': True, 'email': email}), 201
    finally:
        conn.close()


@app.route('/reef/api/auth/login', methods=['POST'])
def login():
    allowed, retry_after = rate_limit('login', max_requests=10, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many login attempts. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT * FROM reef_users WHERE email = ?', [email])
        if not user or not check_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid email or password'}), 401

        # Auto-upgrade legacy SHA-256 hashes to bcrypt on successful login
        if not user['password_hash'].startswith('$2b$'):
            db_execute(conn, 'UPDATE reef_users SET password_hash = ? WHERE id = ?',
                       [hash_password(password), user['id']])
            conn.commit()

        session['reef_user_id'] = user['id']
        return jsonify({
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'],
            'tank_size_gallons': user['tank_size_gallons'],
            'tank_type': user['tank_type'],
            'salt_brand': user['salt_brand'],
            'sump_size_gallons': user['sump_size_gallons'],
            'onboarded': user['onboarded'],
        })
    finally:
        conn.close()


@app.route('/reef/api/auth/logout', methods=['POST'])
def logout():
    session.pop('reef_user_id', None)
    return jsonify({'ok': True})


@app.route('/reef/api/auth/delete-account', methods=['DELETE'])
@require_auth
def delete_account():
    """Permanently delete user account and all associated data (Apple requirement)."""
    uid = session['reef_user_id']
    conn = get_db()
    try:
        # Delete all user data from every table
        # Delete auth codes by email
        user_email = db_fetchone(conn, 'SELECT email FROM reef_users WHERE id = ?', [uid])
        if user_email:
            db_execute(conn, 'DELETE FROM auth_codes WHERE email = ?', [user_email['email']])

        for table in ['parameter_logs', 'livestock', 'equipment', 'chat_history',
                      'maintenance_log', 'calendar_tasks', 'maintenance_schedule',
                      'milestones', 'cost_entries', 'cost_wizard_profile',
                      'recurring_costs']:
            db_execute(conn, f'DELETE FROM {table} WHERE user_id = ?', [uid])

        # Delete tank photo file if exists
        user = db_fetchone(conn, 'SELECT tank_photo FROM reef_users WHERE id = ?', [uid])
        if user and user.get('tank_photo'):
            photo_path = os.path.join(UPLOAD_DIR, user['tank_photo'])
            if os.path.exists(photo_path):
                os.remove(photo_path)

        # Delete the user record
        db_execute(conn, 'DELETE FROM reef_users WHERE id = ?', [uid])
        conn.commit()

        session.pop('reef_user_id', None)
        return jsonify({'ok': True, 'message': 'Account permanently deleted'})
    finally:
        conn.close()


@app.route('/reef/api/auth/me')
@require_auth
def get_me():
    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT * FROM reef_users WHERE id = ?', [session['reef_user_id']])
        if not user:
            session.pop('reef_user_id', None)
            return jsonify({'error': 'User not found'}), 401
        return jsonify({
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'],
            'tank_size_gallons': user['tank_size_gallons'],
            'tank_type': user['tank_type'],
            'salt_brand': user['salt_brand'],
            'sump_size_gallons': user['sump_size_gallons'],
            'onboarded': user['onboarded'],
            'dosing': user.get('dosing', 'none'),
            'fish_count': user.get('fish_count', 0),
            'water_change_schedule': user.get('water_change_schedule', '20_biweekly'),
        })
    finally:
        conn.close()


# ── Email Verification & Password Reset ────────────────────────────────────

@app.route('/reef/api/auth/send-verification', methods=['POST'])
def send_verification():
    allowed, retry_after = rate_limit('verify-send', max_requests=3, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many requests. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email required'}), 400

    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT id FROM reef_users WHERE email = ?', [email])
        if not user:
            # Don't reveal whether email exists
            return jsonify({'ok': True})

        code = generate_code()
        store_code(conn, email, code, 'verify')
        send_email(email, 'ReefPilot — Verify Your Email',
                   f'<h2>Verify Your Email</h2><p>Your verification code is:</p>'
                   f'<h1 style="letter-spacing:8px;font-family:monospace">{code}</h1>'
                   f'<p>This code expires in 15 minutes.</p>')
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/auth/verify-email', methods=['POST'])
def verify_email():
    allowed, retry_after = rate_limit('verify', max_requests=10, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many attempts. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({'error': 'Email and code required'}), 400

    conn = get_db()
    try:
        if not verify_code(conn, email, code, 'verify'):
            return jsonify({'error': 'Invalid or expired code'}), 400

        db_execute(conn, 'UPDATE reef_users SET email_verified = 1 WHERE email = ?', [email])
        conn.commit()

        user = db_fetchone(conn, 'SELECT * FROM reef_users WHERE email = ?', [email])
        session['reef_user_id'] = user['id']
        return jsonify({
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'],
            'onboarded': user['onboarded'],
            'tank_size_gallons': user['tank_size_gallons'],
            'tank_type': user['tank_type'],
            'salt_brand': user['salt_brand'],
            'sump_size_gallons': user['sump_size_gallons'],
        })
    finally:
        conn.close()


@app.route('/reef/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    allowed, retry_after = rate_limit('forgot', max_requests=3, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many requests. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email required'}), 400

    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT id FROM reef_users WHERE email = ?', [email])
        # Always return success to not reveal whether email exists
        if user:
            code = generate_code()
            store_code(conn, email, code, 'reset')
            send_email(email, 'ReefPilot — Reset Your Password',
                       f'<h2>Password Reset</h2><p>Your reset code is:</p>'
                       f'<h1 style="letter-spacing:8px;font-family:monospace">{code}</h1>'
                       f'<p>This code expires in 15 minutes. If you didn\'t request this, ignore this email.</p>')
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/auth/reset-password', methods=['POST'])
def reset_password():
    allowed, retry_after = rate_limit('reset', max_requests=5, window_seconds=300)
    if not allowed:
        return jsonify({'error': f'Too many attempts. Try again in {retry_after}s'}), 429

    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    password = data.get('password', '')

    if not email or not code or not password:
        return jsonify({'error': 'All fields required'}), 400

    pw_error = validate_password(password)
    if pw_error:
        return jsonify({'error': pw_error}), 400

    conn = get_db()
    try:
        if not verify_code(conn, email, code, 'reset'):
            return jsonify({'error': 'Invalid or expired code'}), 400

        db_execute(conn, 'UPDATE reef_users SET password_hash = ? WHERE email = ?',
                   [hash_password(password), email])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Onboarding ──────────────────────────────────────────────────────────────

@app.route('/reef/api/onboard', methods=['PUT'])
@require_auth
def onboard():
    data = request.json or {}
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, '''
            UPDATE reef_users SET
                tank_size_gallons = ?,
                tank_type = ?,
                salt_brand = ?,
                sump_size_gallons = ?,
                onboarded = 1
            WHERE id = ?
        ''', [
            data.get('tank_size_gallons'),
            data.get('tank_type', 'mixed_reef'),
            data.get('salt_brand'),
            data.get('sump_size_gallons'),
            uid
        ])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Onboarding Submit (Structured Wizard) ─────────────────────────────────

DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def _next_weekday(day_name):
    """Return the next occurrence of the given weekday as ISO date string."""
    today = date.today()
    target = DAY_NAMES.index(day_name.lower()) if day_name.lower() in DAY_NAMES else 6
    # Python weekday: Monday=0 ... Sunday=6
    days_ahead = target - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).isoformat()


def _offset_day(day_name, offset):
    """Return the day name offset by N days (e.g. -2 from sunday = friday)."""
    idx = DAY_NAMES.index(day_name.lower()) if day_name.lower() in DAY_NAMES else 6
    return DAY_NAMES[(idx + offset) % 7]


@app.route('/reef/api/onboard/submit', methods=['POST'])
@require_auth
def onboard_submit():
    data = request.json or {}
    uid = session['reef_user_id']
    conn = get_db()
    try:
        # Save profile data
        db_execute(conn, '''
            UPDATE reef_users SET
                tank_size_gallons = ?,
                tank_type = ?,
                salt_brand = ?,
                sump_size_gallons = ?,
                experience_level = ?,
                fish_count = ?,
                dosing = ?,
                water_change_schedule = ?,
                maintenance_day = ?,
                has_sump = ?,
                filtration = ?,
                goals = ?,
                current_problems = ?,
                onboarded = 1
            WHERE id = ?
        ''', [
            data.get('tank_size_gallons'),
            data.get('tank_type', 'mixed_reef'),
            data.get('salt_brand'),
            data.get('sump_size_gallons'),
            data.get('experience'),
            data.get('fish_count', 0),
            data.get('dosing', 'none'),
            data.get('water_change'),
            data.get('maintenance_day', 'sunday'),
            1 if data.get('has_sump') else 0,
            json.dumps(data.get('filtration', [])),
            json.dumps(data.get('goals', [])),
            data.get('current_problems', ''),
            uid
        ])

        # Auto-create calendar tasks based on answers
        maint_day = data.get('maintenance_day', 'sunday')
        wc = data.get('water_change', '20_biweekly')

        if wc == '10_weekly':
            wc_freq, wc_title = 'weekly', 'Water Change (10%)'
        elif wc == '25_monthly':
            wc_freq, wc_title = 'monthly', 'Water Change (25%)'
        else:
            wc_freq, wc_title = 'biweekly', 'Water Change (20%)'

        next_maint = _next_weekday(maint_day)
        test_day = _offset_day(maint_day, -2)

        auto_tasks = [
            (wc_title, wc_freq, maint_day, next_maint, 'water_change'),
            ('Test Water Parameters', 'weekly', test_day, _next_weekday(test_day), 'testing'),
            ('Clean Glass', 'weekly', maint_day, next_maint, 'cleaning'),
            ('Clean Filter Media', 'monthly', maint_day, next_maint, 'cleaning'),
        ]

        if data.get('dosing') in ('manual', 'auto'):
            auto_tasks.append(('Check Dosing Levels', 'weekly', maint_day, next_maint, 'dosing'))

        db_execute(conn, 'DELETE FROM calendar_tasks WHERE user_id = ? AND auto_generated = 1', [uid])
        for title, freq, day, due, cat in auto_tasks:
            db_execute(conn, '''
                INSERT INTO calendar_tasks (user_id, title, frequency, day_of_week, next_due, category, auto_generated)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', [uid, title, freq, day, due, cat])

        conn.commit()

        # Call AI for personalized plan
        import re as re_mod
        questionnaire_summary = json.dumps(data, indent=2)
        system_prompt = ONBOARDING_PLAN_PROMPT.format(questionnaire_json=questionnaire_summary)
        messages = [{'role': 'user', 'content': 'Generate my personalized reef care plan.'}]
        response_text, error = chat_with_ai(messages, system_prompt)

        plan = None
        if not error and response_text:
            json_match = re_mod.search(r'```json\s*(\{.*?\})\s*```', response_text, re_mod.DOTALL)
            if json_match:
                try:
                    plan = json.loads(json_match.group(1))
                except (json.JSONDecodeError, ValueError):
                    pass

        if plan:
            db_execute(conn, 'UPDATE reef_users SET onboard_plan = ? WHERE id = ?',
                       [json.dumps(plan), uid])
            conn.commit()
        else:
            tank_type_label = (data.get('tank_type') or 'mixed_reef').replace('_', ' ')
            plan = {
                'welcome_message': f'Welcome to ReefPilot! Your {data.get("tank_size_gallons", "")} gallon {tank_type_label} is all set up.',
                'tips': ['Log your water parameters regularly', 'Stay consistent with water changes', 'Test before and after changes'],
                'priority_focus': 'Get a baseline by logging your first test results.'
            }

        # Fetch created tasks to return
        tasks = db_fetchall(conn, '''
            SELECT id, title, frequency, day_of_week, next_due, category
            FROM calendar_tasks WHERE user_id = ? ORDER BY next_due ASC
        ''', [uid])

        return jsonify({
            'ok': True,
            'plan': plan,
            'tasks': tasks,
        })
    finally:
        conn.close()


# ── Calendar ──────────────────────────────────────────────────────────────

@app.route('/reef/api/calendar')
@require_auth
def get_calendar():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT * FROM calendar_tasks WHERE user_id = ?
            ORDER BY next_due ASC
        ''', [uid])
        return jsonify({'tasks': rows})
    finally:
        conn.close()


@app.route('/reef/api/calendar/week')
@require_auth
def get_calendar_week():
    uid = session['reef_user_id']
    offset = int(request.args.get('offset', 0))  # week offset from current
    conn = get_db()
    try:
        today = date.today()
        # Start of week (Monday)
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        end = start + timedelta(days=7)
        rows = db_fetchall(conn, '''
            SELECT * FROM calendar_tasks WHERE user_id = ?
            AND next_due >= ? AND next_due < ?
            ORDER BY next_due ASC
        ''', [uid, start.isoformat(), end.isoformat()])
        return jsonify({
            'tasks': rows,
            'week_start': start.isoformat(),
            'week_end': end.isoformat(),
        })
    finally:
        conn.close()


@app.route('/reef/api/calendar/task', methods=['POST'])
@require_auth
def add_calendar_task():
    data = request.json or {}
    uid = session['reef_user_id']
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400

    freq = data.get('frequency', 'once')
    next_due = data.get('next_due') or date.today().isoformat()

    conn = get_db()
    try:
        db_execute(conn, '''
            INSERT INTO calendar_tasks (user_id, title, frequency, next_due, category, auto_generated)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', [uid, title, freq, next_due, data.get('category', 'other')])
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/reef/api/calendar/task/<int:tid>/complete', methods=['PUT'])
@require_auth
def complete_calendar_task(tid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        task = db_fetchone(conn, 'SELECT * FROM calendar_tasks WHERE id = ? AND user_id = ?', [tid, uid])
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        today = date.today()
        freq = task['frequency']

        if freq == 'once':
            db_execute(conn, 'DELETE FROM calendar_tasks WHERE id = ?', [tid])
        else:
            next_due = _calculate_next_due(freq, from_date=today)
            db_execute(conn, '''
                UPDATE calendar_tasks SET last_completed = ?, next_due = ?
                WHERE id = ?
            ''', [today.isoformat(), next_due, tid])

        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/calendar/task/<int:tid>', methods=['DELETE'])
@require_auth
def delete_calendar_task(tid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM calendar_tasks WHERE id = ? AND user_id = ?', [tid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Health Score ───────────────────────────────────────────────────────────

def calculate_health_score(conn, user_id):
    """Calculate a 0-100 health score for a user's tank."""
    score = 50  # Base score

    user = db_fetchone(conn, 'SELECT tank_type FROM reef_users WHERE id = ?', [user_id])
    tank_type = (user or {}).get('tank_type') or 'mixed_reef'
    ranges = PARAMETER_RANGES.get(tank_type, PARAMETER_RANGES['mixed_reef'])

    core_params = ['alkalinity', 'calcium', 'magnesium', 'salinity', 'ph',
                   'nitrate', 'ammonia', 'phosphate', 'temperature']

    # Parameter freshness and range scoring
    for ptype in core_params:
        latest = db_fetchone(conn, '''
            SELECT value, logged_at FROM parameter_logs
            WHERE user_id = ? AND parameter_type = ?
            ORDER BY logged_at DESC LIMIT 1
        ''', [user_id, ptype])

        if not latest:
            continue

        # Freshness check: -10 if not tested in 7+ days
        if latest.get('logged_at'):
            try:
                logged_str = str(latest['logged_at'])
                logged_dt = datetime.fromisoformat(logged_str.replace('Z', '+00:00'))
                if (datetime.now() - logged_dt.replace(tzinfo=None)).days > 7:
                    score -= 10
            except (ValueError, TypeError):
                pass

        # Range scoring
        r = ranges.get(ptype)
        if r and latest.get('value') is not None:
            val = latest['value']
            if r['min'] <= val <= r['max']:
                score += 10  # In ideal range
            elif (r.get('warn_low') is not None and val < r['warn_low']) or \
                 (r.get('warn_high') is not None and val > r['warn_high']):
                score -= 15  # Danger zone
            else:
                score -= 5   # Warning zone

    # Stability bonus: check variance of alk, ca, mg over 30 days
    stability_params = ['alkalinity', 'calcium', 'magnesium']
    stable_count = 0
    for ptype in stability_params:
        if USE_POSTGRES:
            readings = db_fetchall(conn, '''
                SELECT value FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                AND logged_at >= CURRENT_TIMESTAMP - interval '30 days'
                ORDER BY logged_at ASC
            ''', [user_id, ptype])
        else:
            readings = db_fetchall(conn, '''
                SELECT value FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                AND logged_at >= datetime('now', '-30 days')
                ORDER BY logged_at ASC
            ''', [user_id, ptype])
        if len(readings) >= 3:
            values = [r['value'] for r in readings]
            avg = sum(values) / len(values)
            if avg > 0:
                variance_pct = max(abs(v - avg) for v in values) / avg * 100
                if variance_pct < 10:
                    stable_count += 1

    if stable_count == len(stability_params):
        score += 10  # All key params are stable

    # Maintenance bonus: +10 if all tasks are up to date
    if USE_POSTGRES:
        overdue = db_fetchone(conn, '''
            SELECT COUNT(*) as cnt FROM maintenance_schedule
            WHERE user_id = ? AND next_due < CURRENT_DATE
        ''', [user_id])
    else:
        overdue = db_fetchone(conn, '''
            SELECT COUNT(*) as cnt FROM maintenance_schedule
            WHERE user_id = ? AND next_due < date('now')
        ''', [user_id])
    has_tasks = db_fetchone(conn, '''
        SELECT COUNT(*) as cnt FROM maintenance_schedule WHERE user_id = ?
    ''', [user_id])
    if has_tasks and has_tasks['cnt'] > 0 and (not overdue or overdue['cnt'] == 0):
        score += 10

    # Clamp to 0-100
    return max(0, min(100, score))


# ── Tank Photo ─────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

@app.route('/reef/api/tank-photo', methods=['POST'])
@require_auth
def upload_tank_photo():
    uid = session['reef_user_id']
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo uploaded'}), 400
    file = request.files['photo']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': 'Only JPG, PNG, and WebP images allowed'}), 400
    filename = f'{uid}_{uuid.uuid4().hex[:8]}.{ext}'
    filepath = os.path.join(UPLOAD_DIR, filename)
    # Remove old photo if exists
    conn = get_db()
    try:
        old = db_fetchval(conn, 'SELECT tank_photo FROM reef_users WHERE id = ?', [uid])
        if old:
            old_path = os.path.join(UPLOAD_DIR, old)
            if os.path.exists(old_path):
                os.remove(old_path)
        file.save(filepath)
        db_execute(conn, 'UPDATE reef_users SET tank_photo = ? WHERE id = ?', [filename, uid])
        conn.commit()
    finally:
        conn.close()
    return jsonify({'tank_photo_url': f'/reef/api/tank-photo/{filename}'})


@app.route('/reef/api/tank-photo/<filename>')
def serve_tank_photo(filename):
    return send_file(os.path.join(UPLOAD_DIR, secure_filename(filename)))


@app.route('/reef/api/tank-photo', methods=['DELETE'])
@require_auth
def delete_tank_photo():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        old = db_fetchval(conn, 'SELECT tank_photo FROM reef_users WHERE id = ?', [uid])
        if old:
            old_path = os.path.join(UPLOAD_DIR, old)
            if os.path.exists(old_path):
                os.remove(old_path)
            db_execute(conn, 'UPDATE reef_users SET tank_photo = NULL WHERE id = ?', [uid])
            conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


# ── Dashboard ──────────────────────────────────────────────────────────────

@app.route('/reef/api/dashboard')
@require_auth
def dashboard():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        import traceback as _tb
        # Health score
        health_score = calculate_health_score(conn, uid)

        # Latest parameter status
        user = db_fetchone(conn, 'SELECT tank_type, tank_photo FROM reef_users WHERE id = ?', [uid])
        tank_type = (user or {}).get('tank_type') or 'mixed_reef'
        ranges = PARAMETER_RANGES.get(tank_type, PARAMETER_RANGES['mixed_reef'])

        param_status = []
        for ptype, info in PARAMETER_TYPES.items():
            latest = db_fetchone(conn, '''
                SELECT value, unit, logged_at, source FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                ORDER BY logged_at DESC LIMIT 1
            ''', [uid, ptype])

            r = ranges.get(ptype, {})
            status = 'none'
            context_msg = 'No readings yet'
            if latest:
                val = latest['value']
                if r:
                    if r['min'] <= val <= r['max']:
                        status = 'good'
                        context_msg = f'Looking great! Within ideal range ({r["min"]}-{r["max"]})'
                    elif (r.get('warn_low') is not None and val < r['warn_low']) or \
                         (r.get('warn_high') is not None and val > r['warn_high']):
                        status = 'danger'
                        context_msg = f'Outside safe range! Ideal is {r["min"]}-{r["max"]}'
                    else:
                        status = 'warning'
                        context_msg = f'Slightly off — ideal range is {r["min"]}-{r["max"]}'

            param_status.append({
                'type': ptype,
                'label': info['label'],
                'value': latest['value'] if latest else None,
                'unit': info['unit'],
                'logged_at': latest['logged_at'] if latest else None,
                'status': status,
                'context_message': context_msg,
            })

        # Unified tasks: due today or overdue (both sources)
        today_str = date.today().isoformat()
        maint_due = db_fetchall(conn, '''
            SELECT id, task_name, frequency, next_due, notes
            FROM maintenance_schedule WHERE user_id = ?
            AND next_due IS NOT NULL AND next_due <= ?
            ORDER BY next_due ASC
        ''', [uid, today_str])

        cal_due = db_fetchall(conn, '''
            SELECT id, title, frequency, next_due, category
            FROM calendar_tasks WHERE user_id = ? AND next_due <= ?
            ORDER BY next_due ASC
        ''', [uid, today_str])

        due_today = []
        for t in maint_due:
            nd = to_date(t['next_due'])
            due_today.append({
                'id': t['id'], 'source': 'maintenance',
                'title': t['task_name'], 'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']), 'category': 'maintenance',
                'overdue': nd < today if nd else False,
            })
        for t in cal_due:
            nd = to_date(t['next_due'])
            due_today.append({
                'id': t['id'], 'source': 'calendar',
                'title': t['title'], 'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']), 'category': t.get('category', 'other'),
                'overdue': nd < today if nd else False,
            })
        due_today.sort(key=lambda x: (not x['overdue'], x['next_due']))

        # Upcoming tasks (future, not yet due)
        upcoming_maint = db_fetchall(conn, '''
            SELECT id, task_name, frequency, next_due
            FROM maintenance_schedule WHERE user_id = ?
            AND next_due IS NOT NULL AND next_due > ?
            ORDER BY next_due ASC LIMIT 5
        ''', [uid, today_str])

        upcoming_tasks = [{'id': t['id'], 'source': 'maintenance',
            'title': t['task_name'], 'frequency': t['frequency'],
            'next_due': to_date_str(t['next_due'])} for t in upcoming_maint]

        # Has maintenance set up?
        maint_count = db_fetchone(conn, 'SELECT COUNT(*) as cnt FROM maintenance_schedule WHERE user_id = ?', [uid])
        has_maintenance = (maint_count or {}).get('cnt', 0) > 0

        # Active milestones
        active_milestones = db_fetchall(conn, '''
            SELECT id, title, description, category, target_value, current_status
            FROM milestones
            WHERE user_id = ? AND current_status = 'active'
            ORDER BY created_at ASC
        ''', [uid])

        # Recent AI insights — generate from parameter trends
        insights = []
        for ptype in ['alkalinity', 'calcium', 'magnesium', 'nitrate', 'phosphate']:
            readings = db_fetchall(conn, '''
                SELECT value, logged_at FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                ORDER BY logged_at DESC LIMIT 5
            ''', [uid, ptype])
            if len(readings) >= 3:
                values = [r['value'] for r in readings]
                if values[0] > values[-1] * 1.15:
                    insights.append({
                        'type': 'trend_up',
                        'param': ptype,
                        'message': f'{ptype.title()} has been trending upward over recent readings'
                    })
                elif values[0] < values[-1] * 0.85:
                    insights.append({
                        'type': 'trend_down',
                        'param': ptype,
                        'message': f'{ptype.title()} has been trending downward over recent readings'
                    })

        # Monthly cost summary
        if USE_POSTGRES:
            cost_summary = db_fetchall(conn, '''
                SELECT category, SUM(amount) as total FROM cost_entries
                WHERE user_id = ?
                AND purchase_date >= date_trunc('month', CURRENT_DATE)
                GROUP BY category
            ''', [uid])
        else:
            cost_summary = db_fetchall(conn, '''
                SELECT category, SUM(amount) as total FROM cost_entries
                WHERE user_id = ?
                AND purchase_date >= date('now', 'start of month')
                GROUP BY category
            ''', [uid])
        monthly_total = sum(c['total'] for c in cost_summary) if cost_summary else 0

        tank_photo = (user or {}).get('tank_photo')
        tank_photo_url = f'/reef/api/tank-photo/{tank_photo}' if tank_photo else None

        return jsonify({
            'health_score': health_score,
            'param_status': param_status,
            'due_today': due_today,
            'upcoming_tasks': upcoming_tasks,
            'has_maintenance': has_maintenance,
            'active_milestones': active_milestones,
            'insights': insights,
            'cost_summary': {
                'month_total': monthly_total,
                'by_category': cost_summary,
            },
            'tank_photo_url': tank_photo_url,
        })
    except Exception as e:
        _tb.print_exc()
        return jsonify({'error': f'Dashboard error: {str(e)}'}), 500
    finally:
        conn.close()


# ── Cost Tracking ──────────────────────────────────────────────────────────

@app.route('/reef/api/costs', methods=['POST'])
@require_auth
def add_cost():
    data = request.json or {}
    uid = session['reef_user_id']
    category = data.get('category', 'other')
    description = data.get('description', '')
    amount = data.get('amount')
    if amount is None:
        return jsonify({'error': 'Amount is required'}), 400

    conn = get_db()
    try:
        db_execute(conn, '''
            INSERT INTO cost_entries (user_id, category, description, amount, purchase_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [uid, category, description, float(amount),
              data.get('purchase_date', date.today().isoformat()),
              data.get('notes', '')])
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/reef/api/costs', methods=['GET'])
@require_auth
def get_costs():
    uid = session['reef_user_id']
    month = request.args.get('month')  # e.g. "2026-03"
    conn = get_db()
    try:
        if month:
            start = month + '-01'
            if USE_POSTGRES:
                rows = db_fetchall(conn, '''
                    SELECT * FROM cost_entries
                    WHERE user_id = ? AND purchase_date >= ?::date
                      AND purchase_date < (?::date + interval '1 month')
                    ORDER BY purchase_date DESC
                ''', [uid, start, start])
            else:
                rows = db_fetchall(conn, '''
                    SELECT * FROM cost_entries
                    WHERE user_id = ? AND purchase_date >= ? AND purchase_date < date(?, '+1 month')
                    ORDER BY purchase_date DESC
                ''', [uid, start, start])
        else:
            rows = db_fetchall(conn, '''
                SELECT * FROM cost_entries WHERE user_id = ?
                ORDER BY purchase_date DESC LIMIT 100
            ''', [uid])
        return jsonify({'costs': rows})
    finally:
        conn.close()


@app.route('/reef/api/costs/summary')
@require_auth
def cost_summary():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        if USE_POSTGRES:
            rows = db_fetchall(conn, '''
                SELECT
                    to_char(purchase_date, 'YYYY-MM') as month,
                    category,
                    SUM(amount) as total
                FROM cost_entries
                WHERE user_id = ?
                GROUP BY month, category
                ORDER BY month DESC
            ''', [uid])
        else:
            rows = db_fetchall(conn, '''
                SELECT
                    strftime('%%Y-%%m', purchase_date) as month,
                    category,
                    SUM(amount) as total
                FROM cost_entries
                WHERE user_id = ?
                GROUP BY month, category
                ORDER BY month DESC
            ''', [uid])
        return jsonify({'summary': rows})
    finally:
        conn.close()


@app.route('/reef/api/costs/<int:cid>', methods=['DELETE'])
@require_auth
def delete_cost(cid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM cost_entries WHERE id = ? AND user_id = ?', [cid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Reef Lights Data ──────────────────────────────────────────────────

@app.route('/reef/api/lights')
@require_auth
def get_lights():
    """Return reef light brands and models for cost wizard."""
    result = {}
    for key, brand_data in REEF_LIGHTS.items():
        result[key] = {
            'brand': brand_data['brand'],
            'models': {mk: {'name': mv['name'], 'watts': mv['watts']}
                       for mk, mv in brand_data.get('models', {}).items()},
        }
    return jsonify({'lights': result})


# ── Cost Wizard ───────────────────────────────────────────────────────

@app.route('/reef/api/cost-wizard/status')
@require_auth
def cost_wizard_status():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT cost_wizard_completed FROM reef_users WHERE id = ?', [uid])
        completed = bool(user and user.get('cost_wizard_completed'))
        return jsonify({'completed': completed})
    finally:
        conn.close()


@app.route('/reef/api/cost-wizard/submit', methods=['POST'])
@require_auth
def cost_wizard_submit():
    uid = session['reef_user_id']
    data = request.json or {}
    wizard_answers = data.get('answers', [])

    conn = get_db()
    try:
        # Clear existing wizard profile
        db_execute(conn, 'DELETE FROM cost_wizard_profile WHERE user_id = ?', [uid])

        # Insert new answers
        for ans in wizard_answers:
            db_execute(conn, '''
                INSERT INTO cost_wizard_profile (user_id, category, question_key, answer_value, skipped)
                VALUES (?, ?, ?, ?, ?)
            ''', [uid, ans.get('category', ''), ans.get('question_key', ''),
                  str(ans.get('answer_value', '')), 1 if ans.get('skipped') else 0])

        # Get user profile for calculation
        user = db_fetchone(conn, '''
            SELECT tank_size_gallons, sump_size_gallons, water_change_schedule,
                   salt_brand, tank_type, dosing, fish_count
            FROM reef_users WHERE id = ?
        ''', [uid])

        # Build answers dict for calculator
        answers_dict = {}
        for ans in wizard_answers:
            answers_dict[ans['question_key']] = {
                'value': ans.get('answer_value'),
                'skipped': bool(ans.get('skipped')),
            }

        # Calculate costs
        costs = calculate_all_costs(user, answers_dict)

        # Clear existing calculated costs and upsert new ones
        db_execute(conn, "DELETE FROM recurring_costs WHERE user_id = ? AND source = 'calculated'", [uid])
        for c in costs:
            db_execute(conn, '''
                INSERT INTO recurring_costs (user_id, category, description, monthly_amount, source)
                VALUES (?, ?, ?, ?, 'calculated')
                ON CONFLICT (user_id, category, description)
                DO UPDATE SET monthly_amount = EXCLUDED.monthly_amount,
                             source = 'calculated',
                             last_updated = CURRENT_TIMESTAMP
            ''', [uid, c['category'], c['description'], c['monthly_amount']])

        # Mark wizard as completed
        db_execute(conn, 'UPDATE reef_users SET cost_wizard_completed = 1 WHERE id = ?', [uid])

        conn.commit()

        total = sum(c['monthly_amount'] for c in costs)
        return jsonify({'ok': True, 'costs': costs, 'total': total})
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Calculation failed: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/reef/api/cost-wizard/answers')
@require_auth
def cost_wizard_answers():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT category, question_key, answer_value, skipped
            FROM cost_wizard_profile WHERE user_id = ?
        ''', [uid])
        return jsonify({'answers': rows})
    finally:
        conn.close()


@app.route('/reef/api/recurring-costs')
@require_auth
def get_recurring_costs():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        recurring = db_fetchall(conn, '''
            SELECT id, category, description, monthly_amount, source
            FROM recurring_costs WHERE user_id = ?
            ORDER BY monthly_amount DESC
        ''', [uid])

        # Also get manual one-off costs for current month
        if USE_POSTGRES:
            manual = db_fetchall(conn, '''
                SELECT id, category, description, amount, purchase_date
                FROM cost_entries WHERE user_id = ?
                AND purchase_date >= date_trunc('month', CURRENT_DATE)
                ORDER BY purchase_date DESC
            ''', [uid])
        else:
            manual = db_fetchall(conn, '''
                SELECT id, category, description, amount, purchase_date
                FROM cost_entries WHERE user_id = ?
                AND purchase_date >= date('now', 'start of month')
                ORDER BY purchase_date DESC
            ''', [uid])

        recurring_total = sum(r['monthly_amount'] for r in recurring) if recurring else 0
        manual_total = sum(m['amount'] for m in manual) if manual else 0

        return jsonify({
            'recurring': recurring,
            'manual': manual,
            'recurring_total': recurring_total,
            'manual_total': manual_total,
            'total_monthly': recurring_total + manual_total,
        })
    finally:
        conn.close()


@app.route('/reef/api/recurring-costs/<int:rid>', methods=['PUT'])
@require_auth
def update_recurring_cost(rid):
    uid = session['reef_user_id']
    data = request.json or {}
    amount = data.get('monthly_amount')
    if amount is None:
        return jsonify({'error': 'monthly_amount is required'}), 400
    conn = get_db()
    try:
        db_execute(conn, '''
            UPDATE recurring_costs SET monthly_amount = ?, source = 'manual', last_updated = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', [float(amount), rid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/recurring-costs/recalculate', methods=['POST'])
@require_auth
def recalculate_costs():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, '''
            SELECT tank_size_gallons, sump_size_gallons, water_change_schedule,
                   salt_brand, tank_type, dosing, fish_count
            FROM reef_users WHERE id = ?
        ''', [uid])

        rows = db_fetchall(conn, '''
            SELECT question_key, answer_value, skipped
            FROM cost_wizard_profile WHERE user_id = ?
        ''', [uid])

        answers_dict = {}
        for r in rows:
            answers_dict[r['question_key']] = {
                'value': r.get('answer_value'),
                'skipped': bool(r.get('skipped')),
            }

        costs = calculate_all_costs(user, answers_dict)

        db_execute(conn, "DELETE FROM recurring_costs WHERE user_id = ? AND source = 'calculated'", [uid])
        for c in costs:
            db_execute(conn, '''
                INSERT INTO recurring_costs (user_id, category, description, monthly_amount, source)
                VALUES (?, ?, ?, ?, 'calculated')
            ''', [uid, c['category'], c['description'], c['monthly_amount']])

        conn.commit()
        total = sum(c['monthly_amount'] for c in costs)
        return jsonify({'ok': True, 'costs': costs, 'total': total})
    finally:
        conn.close()


# ── Milestones ─────────────────────────────────────────────────────────────

@app.route('/reef/api/milestones')
@require_auth
def get_milestones():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT * FROM milestones WHERE user_id = ?
            ORDER BY CASE current_status
                WHEN 'active' THEN 1
                WHEN 'locked' THEN 2
                WHEN 'completed' THEN 3
            END, created_at ASC
        ''', [uid])
        return jsonify({'milestones': rows})
    finally:
        conn.close()


@app.route('/reef/api/milestones/<int:mid>/complete', methods=['PUT'])
@require_auth
def complete_milestone(mid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, '''
            UPDATE milestones SET current_status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', [mid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Maintenance Schedule ──────────────────────────────────────────────────

@app.route('/reef/api/maintenance')
@require_auth
def get_maintenance():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT * FROM maintenance_schedule WHERE user_id = ?
            ORDER BY next_due ASC
        ''', [uid])
        return jsonify({'tasks': rows})
    finally:
        conn.close()


@app.route('/reef/api/maintenance', methods=['POST'])
@require_auth
def add_maintenance():
    data = request.json or {}
    uid = session['reef_user_id']
    task_name = data.get('task_name', '').strip()
    frequency = data.get('frequency', 'weekly')
    if not task_name:
        return jsonify({'error': 'Task name is required'}), 400

    conn = get_db()
    try:
        next_due = _calculate_next_due(frequency)
        db_execute(conn, '''
            INSERT INTO maintenance_schedule (user_id, task_name, frequency, next_due, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', [uid, task_name, frequency, next_due, data.get('notes', '')])
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/reef/api/maintenance/<int:tid>/done', methods=['PUT'])
@require_auth
def mark_maintenance_done(tid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        task = db_fetchone(conn, '''
            SELECT * FROM maintenance_schedule WHERE id = ? AND user_id = ?
        ''', [tid, uid])
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        today = date.today().isoformat()
        next_due = _calculate_next_due(task['frequency'], from_date=date.today())
        db_execute(conn, '''
            UPDATE maintenance_schedule SET last_done = ?, next_due = ?
            WHERE id = ? AND user_id = ?
        ''', [today, next_due, tid, uid])
        conn.commit()
        return jsonify({'ok': True, 'next_due': next_due})
    finally:
        conn.close()


@app.route('/reef/api/maintenance/<int:tid>', methods=['DELETE'])
@require_auth
def delete_maintenance(tid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM maintenance_schedule WHERE id = ? AND user_id = ?', [tid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


def _calculate_next_due(frequency, from_date=None):
    """Calculate the next due date based on frequency."""
    base = from_date or date.today()
    deltas = {
        'daily': timedelta(days=1),
        'weekly': timedelta(weeks=1),
        'biweekly': timedelta(weeks=2),
        'monthly': timedelta(days=30),
    }
    delta = deltas.get(frequency, timedelta(weeks=1))
    return (base + delta).isoformat()


# ── AI-Generated Maintenance Plan ─────────────────────────────────────────

@app.route('/reef/api/maintenance/generate', methods=['POST'])
@require_auth
def generate_maintenance_plan():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT * FROM reef_users WHERE id = ?', [uid])
        livestock = db_fetchall(conn, 'SELECT * FROM livestock WHERE user_id = ?', [uid])
        equipment = db_fetchall(conn, 'SELECT * FROM equipment WHERE user_id = ?', [uid])

        livestock_summary = 'None'
        if livestock:
            items = [f"{l.get('common_name') or l.get('species', 'Unknown')} ({l.get('category', '')}) x{l.get('quantity', 1)}" for l in livestock]
            livestock_summary = ', '.join(items)

        equipment_summary = 'None'
        if equipment:
            items = [f"{e.get('brand', '')} {e.get('model', '')} ({e.get('category', '')})" for e in equipment]
            equipment_summary = ', '.join(items)

        goals_raw = user.get('goals') or '[]'
        try:
            goals_list = json.loads(goals_raw)
        except (json.JSONDecodeError, TypeError):
            goals_list = []

        problems_raw = user.get('current_problems') or '[]'
        try:
            problems_list = json.loads(problems_raw)
        except (json.JSONDecodeError, TypeError):
            problems_list = []

        system_prompt = MAINTENANCE_PLAN_PROMPT.format(
            experience_level=user.get('experience_level') or 'intermediate',
            tank_size=user.get('tank_size_gallons') or 'Unknown',
            tank_type=user.get('tank_type') or 'mixed_reef',
            salt_brand=user.get('salt_brand') or 'Unknown',
            sump_size=user.get('sump_size_gallons') or 'None',
            tank_age_months=user.get('tank_age_months') or 'Unknown',
            goals=', '.join(goals_list) if goals_list else 'None specified',
            budget_monthly=user.get('budget_monthly') or 'Unknown',
            time_weekly_hours=user.get('time_weekly_hours') or 'Unknown',
            current_problems=', '.join(problems_list) if problems_list else 'None',
            livestock_summary=livestock_summary,
            equipment_summary=equipment_summary,
        )

        messages = [{'role': 'user', 'content': 'Generate my personalized maintenance schedule.'}]
        response_text, error = chat_with_ai(messages, system_prompt)
        if error:
            return jsonify({'error': f'AI error: {error}'}), 500

        # Parse the maintenance plan from the response
        import re
        json_match = re.search(r'```json\s*(\{[^`]*"maintenance_plan"[^`]*\})\s*```', response_text, re.DOTALL)
        if not json_match:
            return jsonify({'error': 'Could not parse maintenance plan from AI response'}), 500

        try:
            plan_data = json.loads(json_match.group(1))
            tasks = plan_data.get('maintenance_plan', [])
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid maintenance plan format'}), 500

        # Clear existing AI-generated schedule and insert new one
        db_execute(conn, 'DELETE FROM maintenance_schedule WHERE user_id = ?', [uid])
        for task in tasks:
            next_due = _calculate_next_due(task.get('frequency', 'weekly'))
            db_execute(conn, '''
                INSERT INTO maintenance_schedule (user_id, task_name, frequency, next_due, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', [uid, task['task_name'], task['frequency'], next_due, task.get('notes', '')])
        conn.commit()

        return jsonify({'ok': True, 'tasks': tasks})
    finally:
        conn.close()


# ── Unified Tasks (Calendar + Maintenance merged) ────────────────────────

@app.route('/reef/api/tasks/upcoming')
@require_auth
def get_tasks_upcoming():
    """Return overdue, today, and upcoming tasks in a single call."""
    uid = session['reef_user_id']
    days = int(request.args.get('days', 7))
    conn = get_db()
    try:
        today = date.today()
        today_str = today.isoformat()
        end = today + timedelta(days=days)
        end_str = end.isoformat()

        cal_rows = db_fetchall(conn, '''
            SELECT id, title, frequency, next_due, category
            FROM calendar_tasks WHERE user_id = ?
            AND next_due <= ? ORDER BY next_due ASC
        ''', [uid, end_str])

        maint_rows = db_fetchall(conn, '''
            SELECT id, task_name, frequency, next_due, notes
            FROM maintenance_schedule WHERE user_id = ?
            AND next_due IS NOT NULL AND next_due <= ?
            ORDER BY next_due ASC
        ''', [uid, end_str])

        overdue, today_tasks, upcoming = [], [], []
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        def classify(task):
            nd_date = to_date(task['next_due'])
            task['next_due'] = nd_date.isoformat() if nd_date else ''
            if not nd_date:
                return
            if nd_date < today:
                diff = (today - nd_date).days
                task['days_overdue'] = diff
                overdue.append(task)
            elif nd_date == today:
                today_tasks.append(task)
            else:
                diff = (nd_date - today).days
                if diff == 1:
                    task['due_label'] = 'Tomorrow'
                else:
                    task['due_label'] = day_names[nd_date.weekday()]
                upcoming.append(task)

        for t in cal_rows:
            classify({
                'id': t['id'], 'source': 'calendar',
                'title': t['title'], 'frequency': t['frequency'],
                'next_due': t['next_due'], 'category': t.get('category', 'other'),
            })
        for t in maint_rows:
            classify({
                'id': t['id'], 'source': 'maintenance',
                'title': t['task_name'], 'frequency': t['frequency'],
                'next_due': t['next_due'], 'category': 'maintenance',
            })

        overdue.sort(key=lambda x: x['next_due'])
        upcoming.sort(key=lambda x: x['next_due'])
        return jsonify({'overdue': overdue, 'today': today_tasks, 'upcoming': upcoming})
    finally:
        conn.close()


@app.route('/reef/api/tasks/week')
@require_auth
def get_tasks_week():
    """Return both calendar_tasks and maintenance_schedule for the week view."""
    uid = session['reef_user_id']
    offset = int(request.args.get('offset', 0))
    conn = get_db()
    try:
        today = date.today()
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        end = start + timedelta(days=7)

        # Calendar tasks in range
        cal_rows = db_fetchall(conn, '''
            SELECT id, title, frequency, next_due, category, last_completed
            FROM calendar_tasks WHERE user_id = ?
            AND next_due >= ? AND next_due < ?
            ORDER BY next_due ASC
        ''', [uid, start.isoformat(), end.isoformat()])

        # Maintenance tasks in range (or overdue)
        maint_rows = db_fetchall(conn, '''
            SELECT id, task_name, frequency, next_due, last_done, notes
            FROM maintenance_schedule WHERE user_id = ?
            AND next_due IS NOT NULL AND next_due < ?
            ORDER BY next_due ASC
        ''', [uid, end.isoformat()])

        # Normalize both into unified task objects
        tasks = []
        for t in cal_rows:
            tasks.append({
                'id': t['id'],
                'source': 'calendar',
                'title': t['title'],
                'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']),
                'category': t.get('category', 'other'),
            })
        for t in maint_rows:
            tasks.append({
                'id': t['id'],
                'source': 'maintenance',
                'title': t['task_name'],
                'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']),
                'category': 'maintenance',
                'notes': t.get('notes', ''),
            })

        tasks.sort(key=lambda x: x['next_due'])

        return jsonify({
            'tasks': tasks,
            'week_start': start.isoformat(),
            'week_end': end.isoformat(),
        })
    finally:
        conn.close()


@app.route('/reef/api/tasks/today')
@require_auth
def get_tasks_today():
    """Return all tasks due today or overdue (both sources)."""
    uid = session['reef_user_id']
    conn = get_db()
    try:
        today_str = date.today().isoformat()

        cal_rows = db_fetchall(conn, '''
            SELECT id, title, frequency, next_due, category
            FROM calendar_tasks WHERE user_id = ? AND next_due <= ?
            ORDER BY next_due ASC
        ''', [uid, today_str])

        maint_rows = db_fetchall(conn, '''
            SELECT id, task_name, frequency, next_due, notes
            FROM maintenance_schedule WHERE user_id = ?
            AND next_due IS NOT NULL AND next_due <= ?
            ORDER BY next_due ASC
        ''', [uid, today_str])

        tasks = []
        for t in cal_rows:
            nd = to_date(t['next_due'])
            tasks.append({
                'id': t['id'], 'source': 'calendar',
                'title': t['title'], 'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']), 'category': t.get('category', 'other'),
                'overdue': nd < today if nd else False,
            })
        for t in maint_rows:
            nd = to_date(t['next_due'])
            tasks.append({
                'id': t['id'], 'source': 'maintenance',
                'title': t['task_name'], 'frequency': t['frequency'],
                'next_due': to_date_str(t['next_due']), 'category': 'maintenance',
                'notes': t.get('notes', ''),
                'overdue': nd < today if nd else False,
            })

        tasks.sort(key=lambda x: (not x['overdue'], x['next_due']))
        return jsonify({'tasks': tasks})
    finally:
        conn.close()


@app.route('/reef/api/tasks/complete', methods=['PUT'])
@require_auth
def complete_unified_task():
    """Complete a task from either source."""
    data = request.json or {}
    source = data.get('source')
    tid = data.get('id')
    uid = session['reef_user_id']

    if not source or not tid:
        return jsonify({'error': 'source and id required'}), 400

    conn = get_db()
    try:
        today = date.today()
        if source == 'maintenance':
            task = db_fetchone(conn, 'SELECT * FROM maintenance_schedule WHERE id = ? AND user_id = ?', [tid, uid])
            if not task:
                return jsonify({'error': 'Task not found'}), 404
            # Use the later of today or current next_due as base, so we always advance forward
            task_due = to_date(task['next_due']) if task['next_due'] else today
            base = max(today, task_due)
            next_due = _calculate_next_due(task['frequency'], from_date=base)
            db_execute(conn, '''
                UPDATE maintenance_schedule SET last_done = ?, next_due = ?
                WHERE id = ? AND user_id = ?
            ''', [today.isoformat(), next_due, tid, uid])
            # Log to maintenance_log for activity history
            db_execute(conn, '''
                INSERT INTO maintenance_log (user_id, task_type, notes)
                VALUES (?, ?, ?)
            ''', [uid, task['task_name'], source])
        elif source == 'calendar':
            task = db_fetchone(conn, 'SELECT * FROM calendar_tasks WHERE id = ? AND user_id = ?', [tid, uid])
            if not task:
                return jsonify({'error': 'Task not found'}), 404
            if task['frequency'] == 'once':
                # Log before deleting
                db_execute(conn, '''
                    INSERT INTO maintenance_log (user_id, task_type, notes)
                    VALUES (?, ?, ?)
                ''', [uid, task['title'], source])
                db_execute(conn, 'DELETE FROM calendar_tasks WHERE id = ?', [tid])
            else:
                task_due = to_date(task['next_due']) if task['next_due'] else today
                base = max(today, task_due)
                next_due = _calculate_next_due(task['frequency'], from_date=base)
                db_execute(conn, '''
                    UPDATE calendar_tasks SET last_completed = ?, next_due = ?
                    WHERE id = ?
                ''', [today.isoformat(), next_due, tid])
                db_execute(conn, '''
                    INSERT INTO maintenance_log (user_id, task_type, notes)
                    VALUES (?, ?, ?)
                ''', [uid, task['title'], source])
        else:
            return jsonify({'error': 'Invalid source'}), 400

        conn.commit()
        deleted = (source == 'calendar' and task['frequency'] == 'once')
        resp = {'ok': True, 'deleted': deleted}
        if not deleted:
            resp['next_due'] = next_due
        return jsonify(resp)
    finally:
        conn.close()


@app.route('/reef/api/tasks/delete', methods=['DELETE'])
@require_auth
def delete_unified_task():
    """Delete a task from either source."""
    data = request.json or {}
    source = data.get('source')
    tid = data.get('id')
    uid = session['reef_user_id']

    if not source or not tid:
        return jsonify({'error': 'source and id required'}), 400

    conn = get_db()
    try:
        if source == 'maintenance':
            db_execute(conn, 'DELETE FROM maintenance_schedule WHERE id = ? AND user_id = ?', [tid, uid])
        elif source == 'calendar':
            db_execute(conn, 'DELETE FROM calendar_tasks WHERE id = ? AND user_id = ?', [tid, uid])
        else:
            return jsonify({'error': 'Invalid source'}), 400
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/tasks/history')
@require_auth
def tasks_history():
    """Return recently completed tasks from maintenance_log."""
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT id, task_type AS title, notes AS category, completed_at
            FROM maintenance_log WHERE user_id = ?
            ORDER BY completed_at DESC LIMIT 10
        ''', [uid])
        return jsonify({'history': [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/reef/api/params/history')
@require_auth
def params_history():
    """Return recent parameter log entries."""
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT id, parameter_type AS type, value, unit, logged_at AS date
            FROM parameter_logs WHERE user_id = ?
            ORDER BY logged_at DESC LIMIT 10
        ''', [uid])
        return jsonify({'entries': [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/reef/api/maintenance/setup', methods=['POST'])
@require_auth
def setup_maintenance():
    """Replace all maintenance tasks with user-chosen ones."""
    data = request.json or {}
    tasks = data.get('tasks', [])
    if not tasks:
        return jsonify({'error': 'No tasks provided'}), 400

    uid = session['reef_user_id']
    conn = get_db()
    try:
        # Clear existing maintenance schedule
        db_execute(conn, 'DELETE FROM maintenance_schedule WHERE user_id = ?', [uid])
        # Insert new tasks
        for t in tasks:
            task_name = (t.get('task_name') or '').strip()
            frequency = t.get('frequency', 'weekly')
            if not task_name:
                continue
            next_due = _calculate_next_due(frequency)
            db_execute(conn, '''
                INSERT INTO maintenance_schedule (user_id, task_name, frequency, next_due, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', [uid, task_name, frequency, next_due, t.get('notes', '')])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/reef/api/maintenance/status')
@require_auth
def maintenance_status():
    """Check if user has set up maintenance tasks."""
    uid = session['reef_user_id']
    conn = get_db()
    try:
        count = db_fetchone(conn, 'SELECT COUNT(*) as cnt FROM maintenance_schedule WHERE user_id = ?', [uid])
        return jsonify({'has_tasks': (count or {}).get('cnt', 0) > 0})
    finally:
        conn.close()


# ── Chat ────────────────────────────────────────────────────────────────────

@app.route('/reef/api/chat', methods=['POST'])
@require_auth
def chat():
    data = request.json or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Message required'}), 400

    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT * FROM reef_users WHERE id = ?', [uid])
        livestock = db_fetchall(conn, 'SELECT * FROM livestock WHERE user_id = ?', [uid])
        recent_params = db_fetchall(conn, '''
            SELECT parameter_type, value, unit, logged_at FROM parameter_logs
            WHERE user_id = ? ORDER BY logged_at DESC LIMIT 20
        ''', [uid])

        # Build system prompt with context
        tank_type = user.get('tank_type') or 'mixed_reef'
        ranges = PARAMETER_RANGES.get(tank_type, PARAMETER_RANGES['mixed_reef'])
        ranges_text = format_ranges_for_prompt(ranges)
        system_prompt = build_system_prompt(user, livestock, recent_params, ranges_text)

        # Load recent chat history
        history = db_fetchall(conn, '''
            SELECT role, content FROM chat_history
            WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
        ''', [uid])
        history.reverse()

        # Build messages list
        messages = [{'role': h['role'], 'content': h['content']} for h in history]
        messages.append({'role': 'user', 'content': message})

        # Call AI
        response_text, error = chat_with_ai(messages, system_prompt)
        if error:
            return jsonify({'error': f'AI error: {error}'}), 500

        # Extract parameters
        extracted = extract_params_from_response(response_text)
        display_text = clean_response(response_text)

        # Save chat messages
        db_execute(conn, '''
            INSERT INTO chat_history (user_id, role, content) VALUES (?, 'user', ?)
        ''', [uid, message])
        db_execute(conn, '''
            INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)
        ''', [uid, display_text])

        # Log extracted parameters
        for p in extracted:
            db_execute(conn, '''
                INSERT INTO parameter_logs (user_id, parameter_type, value, unit, source)
                VALUES (?, ?, ?, ?, 'ai')
            ''', [uid, p['type'], p['value'], p['unit']])

        conn.commit()

        return jsonify({
            'response': display_text,
            'extracted_params': extracted,
        })
    finally:
        conn.close()


@app.route('/reef/api/chat/history')
@require_auth
def chat_history():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        messages = db_fetchall(conn, '''
            SELECT role, content, created_at FROM chat_history
            WHERE user_id = ? ORDER BY created_at ASC LIMIT 100
        ''', [uid])
        return jsonify({'messages': messages})
    finally:
        conn.close()


@app.route('/reef/api/chat/history', methods=['DELETE'])
@require_auth
def clear_chat_history():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM chat_history WHERE user_id = ?', [uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Parameters ──────────────────────────────────────────────────────────────

@app.route('/reef/api/params/status')
@require_auth
def params_status():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, 'SELECT tank_type FROM reef_users WHERE id = ?', [uid])
        tank_type = (user or {}).get('tank_type') or 'mixed_reef'
        ranges = PARAMETER_RANGES.get(tank_type, PARAMETER_RANGES['mixed_reef'])

        results = []
        for ptype, info in PARAMETER_TYPES.items():
            latest = db_fetchone(conn, '''
                SELECT value, unit, logged_at, source FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                ORDER BY logged_at DESC LIMIT 1
            ''', [uid, ptype])

            r = ranges.get(ptype, {})
            status = 'none'
            if latest:
                val = latest['value']
                if r:
                    if r['min'] <= val <= r['max']:
                        status = 'good'
                    elif r.get('warn_low') is not None and val < r['warn_low']:
                        status = 'danger'
                    elif r.get('warn_high') is not None and val > r['warn_high']:
                        status = 'danger'
                    else:
                        status = 'warning'

            results.append({
                'type': ptype,
                'label': info['label'],
                'icon': info['icon'],
                'unit': info['unit'],
                'value': latest['value'] if latest else None,
                'logged_at': latest['logged_at'] if latest else None,
                'source': latest['source'] if latest else None,
                'status': status,
                'range': r,
            })

        return jsonify({'params': results})
    finally:
        conn.close()


@app.route('/reef/api/params/chart')
@require_auth
def params_chart():
    uid = session['reef_user_id']
    ptype = request.args.get('type', 'alkalinity')
    days = int(request.args.get('days', 30))

    conn = get_db()
    try:
        if USE_POSTGRES:
            rows = db_fetchall(conn, '''
                SELECT value, unit, logged_at, source FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                AND logged_at >= CURRENT_TIMESTAMP - (? || ' days')::interval
                ORDER BY logged_at ASC
            ''', [uid, ptype, str(days)])
        else:
            rows = db_fetchall(conn, '''
                SELECT value, unit, logged_at, source FROM parameter_logs
                WHERE user_id = ? AND parameter_type = ?
                AND logged_at >= datetime('now', ?)
                ORDER BY logged_at ASC
            ''', [uid, ptype, f'-{days} days'])

        user = db_fetchone(conn, 'SELECT tank_type FROM reef_users WHERE id = ?', [uid])
        tank_type = (user or {}).get('tank_type') or 'mixed_reef'
        ranges = PARAMETER_RANGES.get(tank_type, PARAMETER_RANGES['mixed_reef'])

        return jsonify({
            'data': rows,
            'range': ranges.get(ptype, {}),
            'param_info': PARAMETER_TYPES.get(ptype, {}),
        })
    finally:
        conn.close()


@app.route('/reef/api/params', methods=['POST'])
@require_auth
def log_params():
    data = request.json or {}
    params = data.get('params', [])
    if not params:
        return jsonify({'error': 'No parameters provided'}), 400

    uid = session['reef_user_id']
    conn = get_db()
    try:
        for p in params:
            ptype = p.get('type')
            value = p.get('value')
            if ptype and value is not None:
                unit = p.get('unit') or PARAMETER_TYPES.get(ptype, {}).get('unit', '')
                db_execute(conn, '''
                    INSERT INTO parameter_logs (user_id, parameter_type, value, unit, source)
                    VALUES (?, ?, ?, ?, 'manual')
                ''', [uid, ptype, float(value), unit])
        conn.commit()
        return jsonify({'ok': True, 'count': len(params)})
    finally:
        conn.close()


# ── Tank profile ────────────────────────────────────────────────────────────

@app.route('/reef/api/tank')
@require_auth
def get_tank():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        user = db_fetchone(conn, '''
            SELECT tank_size_gallons, tank_type, salt_brand, sump_size_gallons, display_name
            FROM reef_users WHERE id = ?
        ''', [uid])
        livestock = db_fetchall(conn, 'SELECT * FROM livestock WHERE user_id = ? ORDER BY added_date DESC', [uid])
        equip = db_fetchall(conn, 'SELECT * FROM equipment WHERE user_id = ? ORDER BY installed_date DESC', [uid])
        return jsonify({
            'profile': user,
            'livestock': livestock,
            'equipment': equip,
            'tank_types': TANK_TYPES,
            'salt_brands': SALT_BRANDS,
        })
    finally:
        conn.close()


@app.route('/reef/api/tank', methods=['PUT'])
@require_auth
def update_tank():
    data = request.json or {}
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, '''
            UPDATE reef_users SET
                tank_size_gallons = ?,
                tank_type = ?,
                salt_brand = ?,
                sump_size_gallons = ?,
                display_name = ?
            WHERE id = ?
        ''', [
            data.get('tank_size_gallons'),
            data.get('tank_type'),
            data.get('salt_brand'),
            data.get('sump_size_gallons'),
            data.get('display_name'),
            uid
        ])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Livestock ───────────────────────────────────────────────────────────────

@app.route('/reef/api/livestock', methods=['GET'])
@require_auth
def get_livestock():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, 'SELECT * FROM livestock WHERE user_id = ? ORDER BY added_date DESC', [uid])
        return jsonify({'livestock': rows})
    finally:
        conn.close()


@app.route('/reef/api/livestock', methods=['POST'])
@require_auth
def add_livestock():
    data = request.json or {}
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, '''
            INSERT INTO livestock (user_id, category, species, common_name, nickname, quantity, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            uid,
            data.get('category', 'fish'),
            data.get('species', ''),
            data.get('common_name', ''),
            data.get('nickname', ''),
            data.get('quantity', 1),
            data.get('notes', ''),
        ])
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/reef/api/livestock/<int:lid>', methods=['DELETE'])
@require_auth
def delete_livestock(lid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM livestock WHERE id = ? AND user_id = ?', [lid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Equipment ───────────────────────────────────────────────────────────────

@app.route('/reef/api/equipment', methods=['GET'])
@require_auth
def get_equipment():
    uid = session['reef_user_id']
    conn = get_db()
    try:
        rows = db_fetchall(conn, 'SELECT * FROM equipment WHERE user_id = ? ORDER BY installed_date DESC', [uid])
        return jsonify({'equipment': rows})
    finally:
        conn.close()


@app.route('/reef/api/equipment', methods=['POST'])
@require_auth
def add_equipment():
    data = request.json or {}
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, '''
            INSERT INTO equipment (user_id, category, brand, model, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', [
            uid,
            data.get('category', 'other'),
            data.get('brand', ''),
            data.get('model', ''),
            data.get('notes', ''),
        ])
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/reef/api/equipment/<int:eid>', methods=['DELETE'])
@require_auth
def delete_equipment(eid):
    uid = session['reef_user_id']
    conn = get_db()
    try:
        db_execute(conn, 'DELETE FROM equipment WHERE id = ? AND user_id = ?', [eid, uid])
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ── Reference data endpoints ───────────────────────────────────────────────

@app.route('/reef/api/data/salt-brands')
def get_salt_brands():
    return jsonify({'brands': SALT_BRANDS})


@app.route('/reef/api/data/tank-types')
def get_tank_types():
    return jsonify({'types': TANK_TYPES})


@app.route('/reef/api/data/param-types')
def get_param_types():
    return jsonify({'types': PARAMETER_TYPES})


# ── Startup ─────────────────────────────────────────────────────────────────

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
