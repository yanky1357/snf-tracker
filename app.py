#!/usr/bin/env python3
"""
SNF Ownership Tracker — Flask API server
Run: python app.py
"""
import re
import sqlite3
from datetime import date
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "snf_ownership.db"

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")

TYPE_MAP = {
    "LLC":             "has_llc",
    "Corporation":     "has_corp",
    "Private Equity":  "has_pe",
    "Holding Company": "has_holding",
    "Investment Firm": "has_investment",
    "Non-Profit":      "has_nonprofit",
    "REIT":            "has_reit",
    "Trust/Trustee":   "has_trust",
}

TYPE_FLAG_COLS = [
    ("LLC",            "llc_owner"),
    ("Corporation",    "corporation_owner"),
    ("Private Equity", "private_equity_owner"),
    ("Holding Co.",    "holding_company_owner"),
    ("Investment Firm","investment_firm_owner"),
    ("Non-Profit",     "non_profit_owner"),
    ("REIT",           "reit_owner"),
    ("Trust/Trustee",  "trust_or_trustee_owner"),
    ("For-Profit",     "for_profit_owner"),
    ("Chain Office",   "chain_home_office_owner"),
    ("Mgmt. Co.",      "management_services_company"),
]


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


def fts_query(q: str):
    """Convert user search string to FTS5 prefix query."""
    cleaned = re.sub(r'[^\w\s]', ' ', q)
    words = [w for w in cleaned.split() if len(w) >= 2]
    if not words:
        return None
    return " ".join(f"{w}*" for w in words)


def owner_types_from_row(row: dict) -> list:
    types = []
    for label, col in TYPE_FLAG_COLS:
        if row.get(col) == "Y":
            types.append(label)
    return types


# ── Static files ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ── API: Search ────────────────────────────────────────────────────────────────

@app.route("/api/search")
def search():
    q          = request.args.get("q", "").strip()
    state      = request.args.get("state", "").strip().upper()
    owner_type = request.args.get("owner_type", "").strip()
    page       = max(1, int(request.args.get("page", 1)))
    per_page   = 20
    offset     = (page - 1) * per_page

    fts = fts_query(q) if q else None
    type_col = TYPE_MAP.get(owner_type)

    con = get_db()
    try:
        # ── Build WHERE additions beyond the base join/match ──────────────────
        extra_where = []
        extra_params = []

        if state:
            extra_where.append("f.facility_state = ?")
            extra_params.append(state)

        if type_col:
            extra_where.append(f"f.{type_col} = 1")

        extra_sql = (" AND " + " AND ".join(extra_where)) if extra_where else ""

        # ── Base query differs for FTS vs. browse-all ─────────────────────────
        if fts:
            base = f"""
                FROM fts_search
                JOIN facilities f ON fts_search.enrollment_id = f.enrollment_id
                LEFT JOIN facility_ccn_map m ON f.enrollment_id = m.enrollment_id
                LEFT JOIN ratings r ON m.ccn = r.ccn
                WHERE fts_search MATCH ?{extra_sql}
            """
            base_params = [fts] + extra_params
        else:
            base = f"""FROM facilities f
                LEFT JOIN facility_ccn_map m ON f.enrollment_id = m.enrollment_id
                LEFT JOIN ratings r ON m.ccn = r.ccn
                WHERE 1=1{extra_sql}"""
            base_params = extra_params

        total = con.execute(
            f"SELECT COUNT(DISTINCT f.enrollment_id) {base}", base_params
        ).fetchone()[0]

        rows = con.execute(
            f"""SELECT DISTINCT f.enrollment_id, f.organization_name,
                       f.facility_state, f.owner_count, f.owner_types,
                       r.overall_rating, r.health_rating, r.qm_rating,
                       r.staffing_rating, r.special_focus, r.abuse_icon,
                       r.total_fines, r.num_penalties, r.provider_name,
                       r.city, r.address
                {base}
                ORDER BY f.organization_name
                LIMIT ? OFFSET ?""",
            base_params + [per_page, offset],
        ).fetchall()

        return jsonify({
            "facilities": [dict(r) for r in rows],
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        })
    except Exception as e:
        return jsonify({"error": str(e), "facilities": [], "total": 0,
                        "page": 1, "per_page": per_page, "total_pages": 1})
    finally:
        con.close()


# ── API: Facility detail ───────────────────────────────────────────────────────

@app.route("/api/facility/<path:enrollment_id>")
def facility(enrollment_id):
    con = get_db()
    try:
        fac = con.execute("""
            SELECT f.*, r.overall_rating, r.health_rating, r.qm_rating,
                   r.staffing_rating, r.special_focus, r.abuse_icon,
                   r.total_fines, r.num_penalties, r.provider_name,
                   r.address, r.city, r.state AS rating_state,
                   r.zip, r.ownership_type, r.num_beds, r.chain_name, m.ccn
            FROM facilities f
            LEFT JOIN facility_ccn_map m ON f.enrollment_id = m.enrollment_id
            LEFT JOIN ratings r ON m.ccn = r.ccn
            WHERE f.enrollment_id = ?
        """, [enrollment_id]).fetchone()
        if not fac:
            return jsonify({"error": "Not found"}), 404

        owners = con.execute("""
            SELECT DISTINCT
                associate_id_owner, type_owner, role_code_owner, role_text_owner,
                first_name_owner, middle_name_owner, last_name_owner, title_owner,
                organization_name_owner, doing_business_as_owner,
                city_owner, state_owner, zip_code_owner, percentage_ownership,
                llc_owner, corporation_owner, private_equity_owner,
                holding_company_owner, investment_firm_owner, non_profit_owner,
                reit_owner, trust_or_trustee_owner, for_profit_owner,
                chain_home_office_owner, management_services_company,
                owned_by_another_org, parent_company_owner, association_date_owner
            FROM ownership
            WHERE enrollment_id = ?
            ORDER BY role_code_owner, organization_name_owner, last_name_owner
        """, [enrollment_id]).fetchall()

        owner_list = []
        for o in owners:
            d = dict(o)
            d["display_name"] = (
                d.get("organization_name_owner") or
                " ".join(filter(None, [
                    d.get("first_name_owner"),
                    d.get("middle_name_owner"),
                    d.get("last_name_owner"),
                ]))
            ).strip() or "Unknown"
            d["types"] = owner_types_from_row(d)
            owner_list.append(d)

        return jsonify({"facility": dict(fac), "owners": owner_list})
    finally:
        con.close()


# ── API: Ownership chain ───────────────────────────────────────────────────────

@app.route("/api/chain/<path:enrollment_id>")
def ownership_chain(enrollment_id):
    con = get_db()
    try:
        fac = con.execute(
            "SELECT enrollment_id, associate_id, organization_name, facility_state "
            "FROM facilities WHERE enrollment_id = ?",
            [enrollment_id]
        ).fetchone()
        if not fac:
            return jsonify({"error": "Not found"}), 404

        visited = set()

        def fetch_owners(assoc_id, depth=0):
            if depth > 6 or assoc_id in visited:
                return []
            visited.add(assoc_id)

            rows = con.execute("""
                SELECT DISTINCT
                    associate_id_owner, type_owner, role_text_owner,
                    first_name_owner, middle_name_owner, last_name_owner,
                    organization_name_owner, city_owner, state_owner,
                    percentage_ownership,
                    llc_owner, corporation_owner, private_equity_owner,
                    holding_company_owner, investment_firm_owner, non_profit_owner,
                    reit_owner, trust_or_trustee_owner, for_profit_owner,
                    chain_home_office_owner, management_services_company,
                    owned_by_another_org
                FROM ownership
                WHERE associate_id = ?
                ORDER BY organization_name_owner, last_name_owner
                LIMIT 100
            """, [assoc_id]).fetchall()

            result = []
            seen_owners = set()
            for r in rows:
                d = dict(r)
                oid = d.get("associate_id_owner", "")
                # Deduplicate by owner id + role combo
                key = (oid, d.get("role_text_owner", ""))
                if key in seen_owners:
                    continue
                seen_owners.add(key)

                name = (
                    d.get("organization_name_owner") or
                    " ".join(filter(None, [
                        d.get("first_name_owner"),
                        d.get("middle_name_owner"),
                        d.get("last_name_owner"),
                    ]))
                ).strip() or "Unknown"

                node = {
                    "associate_id_owner": oid,
                    "display_name":       name,
                    "role":               d.get("role_text_owner", ""),
                    "percentage":         d.get("percentage_ownership", ""),
                    "state":              d.get("state_owner", ""),
                    "types":              owner_types_from_row(d),
                    "owned_by_another":   d.get("owned_by_another_org") == "Y",
                    "children":           [],
                }
                if node["owned_by_another"] and oid and oid not in visited:
                    node["children"] = fetch_owners(oid, depth + 1)
                result.append(node)
            return result

        chain = {
            "enrollment_id": fac["enrollment_id"],
            "display_name":  fac["organization_name"],
            "state":         fac["facility_state"],
            "owners":        fetch_owners(fac["associate_id"]),
        }
        return jsonify(chain)
    finally:
        con.close()


# ── API: States summary (for map) ──────────────────────────────────────────────

@app.route("/api/states")
def states():
    con = get_db()
    try:
        rows = con.execute("""
            SELECT facility_state AS state, COUNT(*) AS count
            FROM facilities
            WHERE facility_state != ''
            GROUP BY facility_state
            ORDER BY facility_state
        """).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        con.close()


@app.route("/api/states/<state>")
def state_facilities(state):
    state = state.upper()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 25
    offset   = (page - 1) * per_page

    con = get_db()
    try:
        total = con.execute(
            "SELECT COUNT(*) FROM facilities WHERE facility_state = ?", [state]
        ).fetchone()[0]

        rows = con.execute("""
            SELECT enrollment_id, organization_name, facility_state,
                   owner_count, owner_types
            FROM facilities
            WHERE facility_state = ?
            ORDER BY organization_name
            LIMIT ? OFFSET ?
        """, [state, per_page, offset]).fetchall()

        return jsonify({
            "state":       state,
            "total":       total,
            "page":        page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "facilities":  [dict(r) for r in rows],
        })
    finally:
        con.close()


# ── API: Owner search ──────────────────────────────────────────────────────────

@app.route("/api/owners/search")
def owners_search():
    q        = request.args.get("q", "").strip()
    state    = request.args.get("state", "").strip().upper()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset   = (page - 1) * per_page

    if not q and not state:
        return jsonify({"owners": [], "total": 0, "page": 1,
                        "per_page": per_page, "total_pages": 1})

    con = get_db()
    try:
        where_parts = ["o.associate_id_owner != ''"]
        params = []

        if q:
            like_q = f"%{q}%"
            where_parts.append(
                "(o.organization_name_owner LIKE ? OR o.first_name_owner LIKE ?"
                " OR o.last_name_owner LIKE ?)"
            )
            params += [like_q, like_q, like_q]

        if state:
            where_parts.append("o.state_owner = ?")
            params.append(state)

        where_sql = "WHERE " + " AND ".join(where_parts)

        inner = f"""
            SELECT
                o.associate_id_owner,
                MAX(CASE WHEN o.organization_name_owner != '' THEN o.organization_name_owner END) AS org_name,
                MAX(o.first_name_owner)  AS first_name,
                MAX(o.middle_name_owner) AS middle_name,
                MAX(o.last_name_owner)   AS last_name,
                MAX(o.title_owner)       AS title,
                MAX(o.city_owner)        AS city,
                MAX(o.state_owner)       AS state,
                MAX(o.zip_code_owner)    AS zip_code,
                MAX(o.type_owner)        AS type_owner,
                MAX(o.llc_owner)                  AS llc_owner,
                MAX(o.corporation_owner)           AS corporation_owner,
                MAX(o.private_equity_owner)        AS private_equity_owner,
                MAX(o.holding_company_owner)       AS holding_company_owner,
                MAX(o.investment_firm_owner)       AS investment_firm_owner,
                MAX(o.non_profit_owner)            AS non_profit_owner,
                MAX(o.reit_owner)                  AS reit_owner,
                MAX(o.trust_or_trustee_owner)      AS trust_or_trustee_owner,
                MAX(o.for_profit_owner)            AS for_profit_owner,
                MAX(o.chain_home_office_owner)     AS chain_home_office_owner,
                MAX(o.management_services_company) AS management_services_company,
                MIN(o.association_date_owner)      AS earliest_date,
                COUNT(DISTINCT o.enrollment_id)    AS facility_count
            FROM ownership o
            {where_sql}
            GROUP BY o.associate_id_owner
        """

        total = con.execute(f"SELECT COUNT(*) FROM ({inner})", params).fetchone()[0]
        rows  = con.execute(
            f"SELECT * FROM ({inner}) ORDER BY facility_count DESC, org_name, last_name LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

        owners = []
        for r in rows:
            d = dict(r)
            d["display_name"] = (
                d.get("org_name") or
                " ".join(filter(None, [d.get("first_name"), d.get("middle_name"), d.get("last_name")]))
            ).strip() or "Unknown"
            d["types"] = owner_types_from_row(d)
            owners.append(d)

        return jsonify({"owners": owners, "total": total, "page": page,
                        "per_page": per_page,
                        "total_pages": max(1, (total + per_page - 1) // per_page)})
    except Exception as e:
        return jsonify({"error": str(e), "owners": [], "total": 0,
                        "page": 1, "per_page": per_page, "total_pages": 1})
    finally:
        con.close()


# ── API: Owner profile ──────────────────────────────────────────────────────────

@app.route("/api/owner/<path:associate_id>")
def owner_profile(associate_id):
    con = get_db()
    try:
        owner_row = con.execute("""
            SELECT
                associate_id_owner,
                MAX(CASE WHEN organization_name_owner != '' THEN organization_name_owner END) AS org_name,
                MAX(first_name_owner)  AS first_name,
                MAX(middle_name_owner) AS middle_name,
                MAX(last_name_owner)   AS last_name,
                MAX(title_owner)       AS title,
                MAX(city_owner)        AS city,
                MAX(state_owner)       AS state,
                MAX(zip_code_owner)    AS zip_code,
                MAX(type_owner)        AS type_owner,
                MAX(llc_owner)                  AS llc_owner,
                MAX(corporation_owner)           AS corporation_owner,
                MAX(private_equity_owner)        AS private_equity_owner,
                MAX(holding_company_owner)       AS holding_company_owner,
                MAX(investment_firm_owner)       AS investment_firm_owner,
                MAX(non_profit_owner)            AS non_profit_owner,
                MAX(reit_owner)                  AS reit_owner,
                MAX(trust_or_trustee_owner)      AS trust_or_trustee_owner,
                MAX(for_profit_owner)            AS for_profit_owner,
                MAX(chain_home_office_owner)     AS chain_home_office_owner,
                MAX(management_services_company) AS management_services_company,
                MIN(association_date_owner)      AS earliest_date,
                COUNT(DISTINCT enrollment_id)    AS facility_count
            FROM ownership
            WHERE associate_id_owner = ?
            GROUP BY associate_id_owner
        """, [associate_id]).fetchone()

        if not owner_row:
            return jsonify({"error": "Not found"}), 404

        owner = dict(owner_row)
        owner["display_name"] = (
            owner.get("org_name") or
            " ".join(filter(None, [owner.get("first_name"), owner.get("middle_name"), owner.get("last_name")]))
        ).strip() or "Unknown"
        owner["types"] = owner_types_from_row(owner)

        fac_rows = con.execute("""
            SELECT
                MIN(o.enrollment_id) AS enrollment_id,
                MAX(COALESCE(f.organization_name, o.enrollment_id)) AS facility_name,
                MAX(f.facility_state) AS facility_state,
                MAX(o.percentage_ownership) AS percentage_ownership,
                GROUP_CONCAT(DISTINCT o.role_text_owner) AS roles,
                MIN(o.association_date_owner) AS association_date_owner,
                MAX(r.overall_rating) AS overall_rating,
                MAX(r.health_rating) AS health_rating,
                MAX(r.qm_rating) AS qm_rating,
                MAX(r.staffing_rating) AS staffing_rating,
                MAX(r.special_focus) AS special_focus,
                MAX(r.abuse_icon) AS abuse_icon,
                MAX(r.total_fines) AS total_fines,
                MAX(r.num_penalties) AS num_penalties,
                MAX(r.provider_name) AS provider_name,
                MAX(r.city) AS rating_city,
                MAX(r.address) AS rating_address,
                MAX(r.chain_id) AS chain_id,
                GROUP_CONCAT(DISTINCT o.enrollment_id) AS all_enrollment_ids
            FROM ownership o
            LEFT JOIN facilities f ON o.enrollment_id = f.enrollment_id
            LEFT JOIN facility_ccn_map m ON o.enrollment_id = m.enrollment_id
            LEFT JOIN ratings r ON m.ccn = r.ccn
            WHERE o.associate_id_owner = ?
            GROUP BY LOWER(TRIM(COALESCE(f.organization_name, o.enrollment_id)))
            ORDER BY facility_name
        """, [associate_id]).fetchall()

        return jsonify({"owner": owner, "facilities": [dict(r) for r in fac_rows]})
    finally:
        con.close()


# ── API: Seller finder ──────────────────────────────────────────────────────────

@app.route("/api/sellers")
def sellers():
    state          = request.args.get("state", "").strip().upper()
    min_yrs        = max(1, int(request.args.get("min_years", 10)))
    max_fac        = max(1, int(request.args.get("max_facilities", 5)))
    min_rating     = request.args.get("min_rating", "").strip()
    ownership_type = request.args.get("ownership_type", "").strip().lower()
    page           = max(1, int(request.args.get("page", 1)))
    per_page   = 25
    offset     = (page - 1) * per_page
    cutoff_year = date.today().year - min_yrs

    con = get_db()
    try:
        state_sql   = "AND state_owner = ?" if state else ""
        state_param = [state] if state else []

        inner = f"""
            SELECT
                o.associate_id_owner,
                MAX(CASE WHEN o.organization_name_owner != '' THEN o.organization_name_owner END) AS org_name,
                MAX(o.first_name_owner)  AS first_name,
                MAX(o.middle_name_owner) AS middle_name,
                MAX(o.last_name_owner)   AS last_name,
                MAX(o.title_owner)       AS title,
                MAX(o.city_owner)        AS city,
                MAX(o.state_owner)       AS state,
                MAX(o.zip_code_owner)    AS zip_code,
                MIN(o.association_date_owner) AS earliest_date,
                COUNT(DISTINCT o.enrollment_id) AS facility_count,
                ROUND(AVG(r.overall_rating), 1) AS avg_overall_rating,
                ROUND(AVG(r.staffing_rating), 1) AS avg_staffing_rating,
                SUM(COALESCE(r.total_fines, 0)) AS total_fines_sum,
                SUM(COALESCE(r.num_penalties, 0)) AS total_penalties,
                MAX(r.ownership_type) AS ownership_type_agg
            FROM ownership o
            LEFT JOIN facility_ccn_map m ON o.enrollment_id = m.enrollment_id
            LEFT JOIN ratings r ON m.ccn = r.ccn
            WHERE o.associate_id_owner != ''
            AND (o.private_equity_owner  IS NULL OR o.private_equity_owner  != 'Y')
            AND (o.reit_owner            IS NULL OR o.reit_owner            != 'Y')
            AND (o.holding_company_owner IS NULL OR o.holding_company_owner != 'Y')
            AND (o.investment_firm_owner IS NULL OR o.investment_firm_owner != 'Y')
            {state_sql}
            GROUP BY o.associate_id_owner
            HAVING facility_count BETWEEN 1 AND ?
            AND earliest_date != ''
            AND CAST(
                CASE WHEN earliest_date LIKE '__/__/____'
                     THEN substr(earliest_date,7,4)
                     WHEN earliest_date LIKE '____-__-__'
                     THEN substr(earliest_date,1,4)
                     ELSE '9999' END
                AS INTEGER
            ) <= ?
        """

        base_params = state_param + [max_fac, cutoff_year]

        # Optional outer WHERE filters (applied after GROUP BY)
        outer_clauses, outer_params = [], []
        if min_rating and min_rating.isdigit():
            outer_clauses.append("avg_overall_rating >= ?")
            outer_params.append(int(min_rating))
        if ownership_type == "for-profit":
            outer_clauses.append("LOWER(ownership_type_agg) LIKE 'for profit%'")
        elif ownership_type == "non-profit":
            outer_clauses.append("LOWER(ownership_type_agg) LIKE 'non profit%'")
        elif ownership_type == "government":
            outer_clauses.append("LOWER(ownership_type_agg) LIKE 'government%'")
        outer_sql = ("WHERE " + " AND ".join(outer_clauses)) if outer_clauses else ""

        total = con.execute(
            f"SELECT COUNT(*) FROM ({inner}) {outer_sql}",
            base_params + outer_params
        ).fetchone()[0]
        rows  = con.execute(
            f"SELECT * FROM ({inner}) {outer_sql} ORDER BY facility_count DESC, earliest_date, state, last_name, org_name LIMIT ? OFFSET ?",
            base_params + outer_params + [per_page, offset],
        ).fetchall()

        def parse_years(raw):
            if not raw or len(raw) < 4:
                return None
            try:
                yr = int(raw[6:10]) if (len(raw) == 10 and raw[2] == "/") else int(raw[:4])
                return max(0, date.today().year - yr)
            except Exception:
                return None

        result = []
        for r in rows:
            d = dict(r)
            d["display_name"] = (
                d.get("org_name") or
                " ".join(filter(None, [d.get("first_name"), d.get("middle_name"), d.get("last_name")]))
            ).strip() or "Unknown"
            d["years_owned"] = parse_years(d.get("earliest_date", ""))
            # Round avg_overall_rating for display
            if d.get("avg_overall_rating") is not None:
                d["avg_overall_rating"] = round(float(d["avg_overall_rating"]), 1)
            result.append(d)

        return jsonify({"sellers": result, "total": total, "page": page,
                        "per_page": per_page,
                        "total_pages": max(1, (total + per_page - 1) // per_page)})
    except Exception as e:
        return jsonify({"error": str(e), "sellers": [], "total": 0,
                        "page": 1, "per_page": per_page, "total_pages": 1})
    finally:
        con.close()


# ── API: Facility profile (rich investor view) ─────────────────────────────

@app.route("/api/profile/<path:enrollment_id>")
def facility_profile_api(enrollment_id):
    con = get_db()
    try:
        fac = con.execute("""
            SELECT f.*, r.overall_rating, r.health_rating, r.qm_rating,
                   r.longstay_qm_rating, r.shortstay_qm_rating,
                   r.staffing_rating, r.special_focus, r.abuse_icon,
                   r.total_fines, r.num_fines, r.num_penalties, r.num_payment_denials,
                   r.provider_name, r.address, r.city, r.state AS rating_state,
                   r.zip, r.ownership_type, r.num_beds, r.avg_daily_census,
                   r.chain_name, r.chain_id, m.ccn,
                   r.ownership_change_last_12mo,
                   r.rn_hours_per_resident_day, r.lpn_hours_per_resident_day,
                   r.cna_hours_per_resident_day, r.total_nurse_hours_per_day,
                   r.weekend_nurse_hours, r.weekend_rn_hours,
                   r.pt_hours_per_resident_day,
                   r.nursing_turnover, r.rn_turnover, r.admin_turnover,
                   r.infection_control_citations,
                   r.cycle1_health_date, r.cycle1_deficiencies,
                   r.cycle1_standard_deficiencies, r.cycle1_complaint_deficiencies,
                   r.cycle1_health_score,
                   r.cycle2_health_date, r.cycle2_deficiencies, r.cycle2_health_score,
                   r.total_weighted_health_score
            FROM facilities f
            LEFT JOIN facility_ccn_map m ON f.enrollment_id = m.enrollment_id
            LEFT JOIN ratings r ON m.ccn = r.ccn
            WHERE f.enrollment_id = ?
        """, [enrollment_id]).fetchone()
        if not fac:
            return jsonify({"error": "Not found"}), 404

        fac_dict = dict(fac)

        owners = con.execute("""
            SELECT DISTINCT
                associate_id_owner, type_owner, role_code_owner, role_text_owner,
                first_name_owner, middle_name_owner, last_name_owner, title_owner,
                organization_name_owner, doing_business_as_owner,
                city_owner, state_owner, zip_code_owner, percentage_ownership,
                llc_owner, corporation_owner, private_equity_owner,
                holding_company_owner, investment_firm_owner, non_profit_owner,
                reit_owner, trust_or_trustee_owner, for_profit_owner,
                chain_home_office_owner, management_services_company,
                owned_by_another_org, parent_company_owner, association_date_owner
            FROM ownership
            WHERE enrollment_id = ?
            ORDER BY role_code_owner, organization_name_owner, last_name_owner
        """, [enrollment_id]).fetchall()

        owner_list = []
        for o in owners:
            d = dict(o)
            d["display_name"] = (
                d.get("organization_name_owner") or
                " ".join(filter(None, [
                    d.get("first_name_owner"),
                    d.get("middle_name_owner"),
                    d.get("last_name_owner"),
                ]))
            ).strip() or "Unknown"
            d["types"] = owner_types_from_row(d)
            owner_list.append(d)

        # owner_since: earliest association_date_owner
        owner_since = None
        for o in owner_list:
            raw = o.get("association_date_owner") or ""
            if raw:
                try:
                    yr = int(raw[6:10]) if (len(raw) == 10 and raw[2] == "/") else int(raw[:4])
                    if owner_since is None or yr < owner_since:
                        owner_since = yr
                except Exception:
                    pass

        has_pe = any(o.get("private_equity_owner") == "Y" for o in owner_list)

        # state averages
        fac_state = fac_dict.get("facility_state") or ""
        state_avgs = {"avg_overall": None, "avg_staffing": None, "avg_total_fines": None,
                      "avg_rn_hours": None, "avg_nurse_hours": None,
                      "avg_nursing_turnover": None, "avg_occupancy": None, "count": 0}
        if fac_state:
            sa = con.execute("""
                SELECT ROUND(AVG(r.overall_rating),2) AS avg_overall,
                       ROUND(AVG(r.staffing_rating),2) AS avg_staffing,
                       ROUND(AVG(COALESCE(r.total_fines,0)),0) AS avg_total_fines,
                       ROUND(AVG(r.rn_hours_per_resident_day),2) AS avg_rn_hours,
                       ROUND(AVG(r.total_nurse_hours_per_day),2) AS avg_nurse_hours,
                       ROUND(AVG(r.nursing_turnover),1) AS avg_nursing_turnover,
                       ROUND(AVG(CASE WHEN r.num_beds > 0 THEN r.avg_daily_census * 1.0 / r.num_beds * 100 END),1) AS avg_occupancy,
                       COUNT(*) AS count
                FROM ratings r
                JOIN facility_ccn_map m ON r.ccn = m.ccn
                JOIN facilities f ON m.enrollment_id = f.enrollment_id
                WHERE f.facility_state = ?
            """, [fac_state]).fetchone()
            if sa:
                def _r(v, digits=2): return round(v, digits) if v is not None else None
                state_avgs = {
                    "avg_overall":          _r(sa["avg_overall"]),
                    "avg_staffing":         _r(sa["avg_staffing"]),
                    "avg_total_fines":      _r(sa["avg_total_fines"] or 0, 0),
                    "avg_rn_hours":         _r(sa["avg_rn_hours"]),
                    "avg_nurse_hours":      _r(sa["avg_nurse_hours"]),
                    "avg_nursing_turnover": _r(sa["avg_nursing_turnover"], 1),
                    "avg_occupancy":        _r(sa["avg_occupancy"], 1),
                    "count":                sa["count"],
                }

        # investor grade
        overall    = fac_dict.get("overall_rating")
        health     = fac_dict.get("health_rating")
        staffing   = fac_dict.get("staffing_rating")
        qm         = fac_dict.get("qm_rating")
        total_fines   = fac_dict.get("total_fines") or 0
        num_penalties = fac_dict.get("num_penalties") or 0
        special_focus = fac_dict.get("special_focus") or ""
        abuse_icon    = fac_dict.get("abuse_icon") or ""

        score = 0.0
        if overall  is not None: score += (overall  / 5) * 30
        if health   is not None: score += (health   / 5) * 20
        if staffing is not None: score += (staffing / 5) * 20
        if qm       is not None: score += (qm       / 5) * 15

        if   total_fines > 100000: score -= 15
        elif total_fines >  50000: score -= 10
        elif total_fines >  10000: score -= 5

        if   num_penalties > 10: score -= 10
        elif num_penalties >  5: score -= 5

        if special_focus:     score -= 15
        if abuse_icon == "Y": score -= 10
        if has_pe:            score -= 5

        score = max(0.0, min(100.0, score))

        if   score >= 85: grade = "A"
        elif score >= 75: grade = "A-"
        elif score >= 65: grade = "B+"
        elif score >= 55: grade = "B"
        elif score >= 45: grade = "B-"
        elif score >= 35: grade = "C+"
        elif score >= 25: grade = "C"
        elif score >= 15: grade = "C-"
        else:             grade = "D"

        # signals
        signals = []
        if special_focus:
            signals.append({"level":"red",
                "text":"Special Focus Facility — on CMS watch list",
                "sub":"Indicates persistent quality issues requiring federal oversight"})
        if abuse_icon == "Y":
            signals.append({"level":"red",
                "text":"Abuse icon active — CMS has flagged this facility",
                "sub":"Significant compliance and liability risk for buyers"})
        if total_fines > 50000:
            signals.append({"level":"red",
                "text":f"High penalty history — ${total_fines:,.0f} in total fines",
                "sub":f"{num_penalties} penalties on record — review inspection reports before acquisition"})
        elif total_fines > 10000:
            signals.append({"level":"amber",
                "text":f"Moderate fine history — ${total_fines:,.0f} in total fines",
                "sub":f"{num_penalties} penalties on record"})
        if staffing is not None:
            if staffing <= 2:
                signals.append({"level":"amber",
                    "text":"Staffing rating below average",
                    "sub":"Common operational issue that suppresses occupancy and revenue"})
            elif staffing >= 4:
                signals.append({"level":"green",
                    "text":"Strong staffing rating — 4+ stars",
                    "sub":"Indicates stable workforce, lower operational risk"})
        if overall is not None and overall >= 4:
            signals.append({"level":"green",
                "text":f"Strong overall CMS rating — {int(overall)} stars",
                "sub":"High-quality facilities command premium acquisition prices"})
        if has_pe:
            signals.append({"level":"amber",
                "text":"Private equity in ownership chain",
                "sub":"PE-owned facilities may have structured debt — verify capital stack before offer"})
        if not signals:
            signals.append({"level":"green",
                "text":"No major red flags detected in CMS data",
                "sub":"Standard due diligence still recommended"})

        return jsonify({
            "facility":       fac_dict,
            "owners":         owner_list,
            "investor_grade": grade,
            "investor_score": round(score, 1),
            "signals":        signals,
            "owner_since":    owner_since,
            "has_pe":         has_pe,
            "state_avgs":     state_avgs,
            "owner_count":    len(owner_list),
        })
    finally:
        con.close()


@app.route("/facility")
def facility_profile_page():
    return send_from_directory(app.static_folder, "profile.html")


@app.route("/api/quality-measures/<path:enrollment_id>")
def quality_measures(enrollment_id):
    con = get_db()
    try:
        ccn_row = con.execute(
            "SELECT ccn FROM facility_ccn_map WHERE enrollment_id = ?", [enrollment_id]
        ).fetchone()
        if not ccn_row:
            return jsonify({"measures": []})
        rows = con.execute("""
            SELECT measure_code, measure_desc, resident_type,
                   q1_score, q2_score, q3_score, q4_score, avg_score, used_in_rating
            FROM quality_measures WHERE ccn = ?
            ORDER BY resident_type DESC, measure_code
        """, [ccn_row["ccn"]]).fetchall()
        return jsonify({"measures": [dict(r) for r in rows]})
    finally:
        con.close()


@app.route("/api/chain-performance/<path:chain_id>")
def chain_performance(chain_id):
    con = get_db()
    try:
        chain = con.execute(
            "SELECT * FROM chain_performance WHERE chain_id = ?", [chain_id]
        ).fetchone()
        if not chain:
            return jsonify({"error": "Chain not found"}), 404
        national = con.execute(
            "SELECT * FROM chain_performance WHERE chain_id = 'NATIONAL'"
        ).fetchone()
        return jsonify({
            "chain": dict(chain),
            "national": dict(national) if national else None,
        })
    finally:
        con.close()


@app.route("/api/financials/<path:enrollment_id>")
def financials(enrollment_id):
    con = get_db()
    try:
        row = con.execute("""
            SELECT cr.*,
                   ROUND(AVG(cr2.net_patient_revenue),0) AS state_avg_revenue,
                   ROUND(AVG(cr2.operating_expense),0)   AS state_avg_expense,
                   ROUND(AVG(cr2.operating_income),0)    AS state_avg_op_income,
                   ROUND(AVG(CASE WHEN cr2.total_days > 0
                        THEN cr2.medicare_days * 100.0 / cr2.total_days END), 1) AS state_avg_medicare_pct,
                   ROUND(AVG(CASE WHEN cr2.total_days > 0
                        THEN cr2.medicaid_days * 100.0 / cr2.total_days END), 1) AS state_avg_medicaid_pct
            FROM facility_ccn_map m
            JOIN cost_reports cr ON cr.ccn = m.ccn
            JOIN cost_reports cr2 ON cr2.state = cr.state
            WHERE m.enrollment_id = ?
        """, [enrollment_id]).fetchone()
        if not row or row["net_patient_revenue"] is None:
            return jsonify({"available": False})
        d = dict(row)
        d["available"] = True
        # Compute payer mix percentages
        total = d.get("total_days") or 0
        d["medicare_pct"] = round((d["medicare_days"] or 0) * 100 / total, 1) if total else None
        d["medicaid_pct"] = round((d["medicaid_days"] or 0) * 100 / total, 1) if total else None
        d["other_pct"]    = round((d["other_days"]    or 0) * 100 / total, 1) if total else None
        # Profit margin
        rev = d.get("net_patient_revenue") or 0
        d["profit_margin"] = round((d["operating_income"] or 0) * 100 / rev, 1) if rev else None
        d["payroll_pct"]   = round((d["total_salaries"]   or 0) * 100 / rev, 1) if rev else None
        return jsonify(d)
    finally:
        con.close()


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not DB_PATH.exists():
        print("ERROR: Database not found. Run 'python build_db.py' first.")
    else:
        print("Starting SNF Ownership Tracker at http://localhost:5000")
        app.run(host="0.0.0.0", port=5001, debug=False)
