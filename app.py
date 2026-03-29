#!/usr/bin/env python3
"""NourishNY — Flask API server for food delivery program applications."""

import os
import json
import sqlite3
import re
import threading
import urllib.request
import urllib.error
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for, Response

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'nourishny-dev-key-change-in-prod')

DB_PATH = os.environ.get('DB_PATH', 'nourishny.db')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Email config — set these environment variables in production
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
ADMIN_NOTIFY_EMAIL = os.environ.get('ADMIN_NOTIFY_EMAIL', '')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5001')


# ── Database helpers ─────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    """Create the database if it doesn't exist."""
    if not os.path.exists(DB_PATH):
        import build_db
        build_db.build()


# ── Email helpers ────────────────────────────────────────────────────────────

def send_email(to_email, subject, html_body):
    """Send an email via Resend API in a background thread."""
    if not RESEND_API_KEY:
        print(f'[EMAIL SKIPPED] No RESEND_API_KEY configured. Would send to {to_email}: {subject}')
        return

    def _send():
        try:
            payload = json.dumps({
                'from': 'NourishNY <onboarding@resend.dev>',
                'to': [to_email],
                'subject': subject,
                'html': html_body
            }).encode('utf-8')

            req = urllib.request.Request(
                'https://api.resend.com/emails',
                data=payload,
                headers={
                    'Authorization': f'Bearer {RESEND_API_KEY}',
                    'Content-Type': 'application/json'
                },
                method='POST'
            )
            resp = urllib.request.urlopen(req, timeout=10)
            body = resp.read().decode('utf-8')
            print(f'[EMAIL SENT] To: {to_email} Subject: {subject} Status: {resp.status} Response: {body}')
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f'[EMAIL ERROR] Status: {e.code} Response: {error_body}')
        except Exception as e:
            print(f'[EMAIL ERROR] {e}')

    threading.Thread(target=_send, daemon=True).start()


def send_admin_notification(data):
    """Notify admin of a new application."""
    if not ADMIN_NOTIFY_EMAIL:
        return
    health = ', '.join(data.get('health_categories', [])) or 'None'
    members = data.get('household_members', [])
    member_count = len(members)

    send_email(
        ADMIN_NOTIFY_EMAIL,
        f'New Application: {data["first_name"]} {data["last_name"]}',
        f'''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:#2D5016;color:white;padding:20px;border-radius:8px 8px 0 0;">
                <h2 style="margin:0;">New Application Received</h2>
            </div>
            <div style="background:#fff;padding:24px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;">
                <h3 style="color:#2D5016;margin-top:0;">{data["first_name"]} {data["last_name"]}</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="padding:6px 0;color:#888;width:140px;">Medicaid ID</td><td style="padding:6px 0;font-weight:600;">{data["medicaid_id"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">Phone</td><td style="padding:6px 0;">{data["cell_phone"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">Email</td><td style="padding:6px 0;">{data["email"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">Address</td><td style="padding:6px 0;">{data["street_address"]}, {data["city"]}, NY {data["zipcode"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">Health Categories</td><td style="padding:6px 0;">{health}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">Household Members</td><td style="padding:6px 0;">{member_count} additional</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">SNAP</td><td style="padding:6px 0;">{data["has_snap"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">WIC</td><td style="padding:6px 0;">{data["has_wic"]}</td></tr>
                    <tr><td style="padding:6px 0;color:#888;">New Applicant</td><td style="padding:6px 0;">{data["is_new_applicant"]}</td></tr>
                </table>
                <div style="margin-top:20px;">
                    <a href="{SITE_URL}/admin" style="background:#2D5016;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;">View in Dashboard</a>
                </div>
            </div>
        </div>
        '''
    )


def send_applicant_confirmation(data):
    """Send confirmation email to the applicant."""
    send_email(
        data['email'],
        'NourishNY — Application Received!',
        f'''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:#2D5016;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
                <h2 style="margin:0;">NourishNY</h2>
                <p style="margin:4px 0 0;opacity:0.9;">Free Healthy Meals Delivered to Your Door</p>
            </div>
            <div style="background:#fff;padding:24px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;">
                <h3 style="color:#2D5016;">Hi {data["first_name"]},</h3>
                <p>Thank you for applying to NourishNY! We've received your application and our team will review it shortly.</p>

                <div style="background:#FAF9F6;border-radius:8px;padding:16px;margin:16px 0;">
                    <h4 style="color:#2D5016;margin-top:0;">What happens next?</h4>
                    <p style="margin:8px 0;"><strong>1. Review</strong> — We'll verify your eligibility and Medicaid information.</p>
                    <p style="margin:8px 0;"><strong>2. Confirmation</strong> — You'll receive a call or email confirming your enrollment.</p>
                    <p style="margin:8px 0;"><strong>3. Delivery</strong> — Once enrolled, your food deliveries will begin on a regular schedule.</p>
                </div>

                <p style="color:#888;font-size:14px;">If you have any questions, please don't hesitate to reach out.</p>
                <p style="color:#2D5016;font-weight:600;">— The NourishNY Team</p>
            </div>
            <div style="text-align:center;padding:16px;color:#888;font-size:12px;">
                NourishNY &mdash; An SCN Approved Vendor serving New York families.
            </div>
        </div>
        '''
    )


# ── Page routes ──────────────────────────────────────────────────────────────

@app.route('/')
def landing():
    return send_from_directory('static', 'index.html')


@app.route('/apply')
def apply_page():
    return send_from_directory('static', 'apply.html')


@app.route('/thank-you')
def thank_you():
    return send_from_directory('static', 'thankyou.html')


@app.route('/admin')
def admin_page():
    return send_from_directory('static', 'admin.html')


# ── API: Submit application ──────────────────────────────────────────────────

@app.route('/api/apply', methods=['POST'])
def submit_application():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Required fields
    required = [
        'first_name', 'last_name', 'date_of_birth', 'medicaid_id',
        'cell_phone', 'email', 'street_address', 'city', 'state', 'zipcode',
        'is_employed', 'spouse_employed', 'has_wic', 'has_snap', 'is_new_applicant'
    ]
    missing = [f for f in required if not data.get(f, '').strip()]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate Medicaid ID format: 2 letters + 5 digits + 1 letter
    mid = data['medicaid_id'].strip().upper()
    if not re.match(r'^[A-Z]{2}\d{5}[A-Z]$', mid):
        return jsonify({'error': 'Invalid Medicaid ID format. Must be 2 letters + 5 numbers + 1 letter (e.g., AB12345C)'}), 400

    # Validate state is NY
    if data['state'].strip().upper() != 'NY':
        return jsonify({'error': 'Address must be in New York state'}), 400

    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO applications (
                first_name, last_name, date_of_birth, medicaid_id,
                cell_phone, home_phone, email,
                street_address, apt_unit, city, state, zipcode,
                health_categories,
                is_employed, spouse_employed, has_wic, has_snap,
                food_allergies, is_new_applicant,
                household_members
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['first_name'].strip(),
            data['last_name'].strip(),
            data['date_of_birth'].strip(),
            mid,
            data['cell_phone'].strip(),
            data.get('home_phone', '').strip() or None,
            data['email'].strip(),
            data['street_address'].strip(),
            data.get('apt_unit', '').strip() or None,
            data['city'].strip(),
            'NY',
            data['zipcode'].strip(),
            json.dumps(data.get('health_categories', [])),
            data['is_employed'],
            data['spouse_employed'],
            data['has_wic'],
            data['has_snap'],
            data.get('food_allergies', '').strip() or None,
            data['is_new_applicant'],
            json.dumps(data.get('household_members', []))
        ))
        conn.commit()

        # Send emails (non-blocking, runs in background threads)
        send_admin_notification(data)
        send_applicant_confirmation(data)

        return jsonify({'success': True, 'message': 'Application submitted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ── Admin API ────────────────────────────────────────────────────────────────

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if data and data.get('password') == ADMIN_PASSWORD:
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid password'}), 401


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/api/admin/applications')
@require_admin
def list_applications():
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = 25

    conn = get_db()
    query = 'SELECT * FROM applications WHERE 1=1'
    params = []

    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)

    if search:
        query += ''' AND (
            first_name LIKE ? OR last_name LIKE ? OR
            medicaid_id LIKE ? OR email LIKE ? OR cell_phone LIKE ?
        )'''
        s = f'%{search}%'
        params.extend([s, s, s, s, s])

    # Count total
    count_q = query.replace('SELECT *', 'SELECT COUNT(*)')
    total = conn.execute(count_q, params).fetchone()[0]

    # Fetch page
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    rows = conn.execute(query, params).fetchall()
    apps = [dict(r) for r in rows]

    # Parse JSON fields
    for a in apps:
        try:
            a['health_categories'] = json.loads(a['health_categories'] or '[]')
        except (json.JSONDecodeError, TypeError):
            a['health_categories'] = []
        try:
            a['household_members'] = json.loads(a['household_members'] or '[]')
        except (json.JSONDecodeError, TypeError):
            a['household_members'] = []

    conn.close()
    return jsonify({
        'applications': apps,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page
    })


@app.route('/api/admin/applications/<int:app_id>')
@require_admin
def get_application(app_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Application not found'}), 404

    a = dict(row)
    try:
        a['health_categories'] = json.loads(a['health_categories'] or '[]')
    except (json.JSONDecodeError, TypeError):
        a['health_categories'] = []
    try:
        a['household_members'] = json.loads(a['household_members'] or '[]')
    except (json.JSONDecodeError, TypeError):
        a['household_members'] = []
    return jsonify(a)


@app.route('/api/admin/applications/<int:app_id>/status', methods=['PUT'])
@require_admin
def update_status(app_id):
    data = request.get_json()
    status = data.get('status')
    notes = data.get('admin_notes')
    if status not in ('new', 'reviewed', 'enrolled', 'rejected'):
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_db()
    conn.execute(
        'UPDATE applications SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?',
        (status, notes, datetime.now().isoformat(), app_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/export')
@require_admin
def export_csv():
    import csv
    import io

    conn = get_db()
    rows = conn.execute('SELECT * FROM applications ORDER BY created_at DESC').fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(list(row))

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=applications.csv'}
    )


@app.route('/api/admin/stats')
@require_admin
def admin_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
    new = conn.execute("SELECT COUNT(*) FROM applications WHERE status = 'new'").fetchone()[0]
    enrolled = conn.execute("SELECT COUNT(*) FROM applications WHERE status = 'enrolled'").fetchone()[0]
    reviewed = conn.execute("SELECT COUNT(*) FROM applications WHERE status = 'reviewed'").fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM applications WHERE status = 'rejected'").fetchone()[0]
    conn.close()
    return jsonify({
        'total': total, 'new': new, 'enrolled': enrolled,
        'reviewed': reviewed, 'rejected': rejected
    })


# ── QR Code ──────────────────────────────────────────────────────────────────

@app.route('/qr')
def qr_code_page():
    return send_from_directory('static', 'qr.html')


@app.route('/api/qr')
def generate_qr():
    """Generate a QR code PNG that points to the site."""
    import io
    try:
        import qrcode
    except ImportError:
        return jsonify({'error': 'qrcode package not installed. Run: pip install qrcode[pil]'}), 500

    url = request.args.get('url', SITE_URL)
    size = int(request.args.get('size', 10))

    qr = qrcode.QRCode(version=1, box_size=size, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#2D5016', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return Response(buf.getvalue(), mimetype='image/png',
                    headers={'Content-Disposition': 'inline; filename=nourishny-qr.png'})


# ── Init & Run ───────────────────────────────────────────────────────────────

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
