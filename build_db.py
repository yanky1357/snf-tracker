#!/usr/bin/env python3
"""
Build SQLite database from SNF ownership CSV files.
Run once: python build_db.py
"""
import csv
import glob
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "snf_ownership.db"
CSV_PATTERN = str(Path(__file__).parent / "SNF_All_Owners_2026.03.02_*.csv")
CHAIN_PERF_CSV = "/Users/yakovwider/Downloads/2026-02/Chain_Performance_20260311.csv"

# Maps (sqlite column name, CSV column header)
COLUMNS = [
    ("enrollment_id",               "ENROLLMENT ID"),
    ("associate_id",                "ASSOCIATE ID"),
    ("organization_name",           "ORGANIZATION NAME"),
    ("associate_id_owner",          "ASSOCIATE ID - OWNER"),
    ("type_owner",                  "TYPE - OWNER"),
    ("role_code_owner",             "ROLE CODE - OWNER"),
    ("role_text_owner",             "ROLE TEXT - OWNER"),
    ("association_date_owner",      "ASSOCIATION DATE - OWNER"),
    ("first_name_owner",            "FIRST NAME - OWNER"),
    ("middle_name_owner",           "MIDDLE NAME - OWNER"),
    ("last_name_owner",             "LAST NAME - OWNER"),
    ("title_owner",                 "TITLE - OWNER"),
    ("organization_name_owner",     "ORGANIZATION NAME - OWNER"),
    ("doing_business_as_owner",     "DOING BUSINESS AS NAME - OWNER"),
    ("address_line_1_owner",        "ADDRESS LINE 1 - OWNER"),
    ("address_line_2_owner",        "ADDRESS LINE 2 - OWNER"),
    ("city_owner",                  "CITY - OWNER"),
    ("state_owner",                 "STATE - OWNER"),
    ("zip_code_owner",              "ZIP CODE - OWNER"),
    ("percentage_ownership",        "PERCENTAGE OWNERSHIP"),
    ("created_for_acquisition",     "CREATED FOR ACQUISITION - OWNER"),
    ("corporation_owner",           "CORPORATION - OWNER"),
    ("llc_owner",                   "LLC - OWNER"),
    ("medical_provider_supplier",   "MEDICAL PROVIDER SUPPLIER - OWNER"),
    ("management_services_company", "MANAGEMENT SERVICES COMPANY - OWNER"),
    ("medical_staffing_company",    "MEDICAL STAFFING COMPANY - OWNER"),
    ("holding_company_owner",       "HOLDING COMPANY - OWNER"),
    ("investment_firm_owner",       "INVESTMENT FIRM - OWNER"),
    ("financial_institution_owner", "FINANCIAL INSTITUTION - OWNER"),
    ("consulting_firm_owner",       "CONSULTING FIRM - OWNER"),
    ("for_profit_owner",            "FOR PROFIT - OWNER"),
    ("non_profit_owner",            "NON PROFIT - OWNER"),
    ("private_equity_owner",        "PRIVATE EQUITY COMPANY - OWNER"),
    ("reit_owner",                  "REIT - OWNER"),
    ("chain_home_office_owner",     "CHAIN HOME OFFICE - OWNER"),
    ("trust_or_trustee_owner",      "TRUST OR TRUSTEE - OWNER"),
    ("other_type_owner",            "OTHER TYPE - OWNER"),
    ("other_type_text_owner",       "OTHER TYPE TEXT - OWNER"),
    ("parent_company_owner",        "PARENT COMPANY - OWNER"),
    ("owned_by_another_org",        "OWNED BY ANOTHER ORG OR IND - OWNER"),
]

COL_NAMES = [c[0] for c in COLUMNS]
CSV_HEADERS = [c[1] for c in COLUMNS]


def build():
    t0 = time.time()

    if DB_PATH.exists():
        print(f"Removing existing {DB_PATH.name} ...")
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA cache_size=-64000")  # 64 MB cache

    # ── 1. ownership table ────────────────────────────────────────────────────
    col_defs = ",\n    ".join(f"{c} TEXT" for c in COL_NAMES)
    cur.execute(f"""
        CREATE TABLE ownership (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {col_defs}
        )
    """)
    con.commit()

    files = sorted(
        glob.glob(CSV_PATTERN),
        key=lambda x: int(Path(x).stem.split("_")[-1]),
    )
    if not files:
        print("ERROR: No CSV files found matching", CSV_PATTERN)
        return

    print(f"Loading {len(files)} CSV files...")
    placeholders = ",".join(["?"] * len(COL_NAMES))
    insert_sql = f"INSERT INTO ownership ({','.join(COL_NAMES)}) VALUES ({placeholders})"

    total = 0
    for i, f in enumerate(files, 1):
        batch = []
        with open(f, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                batch.append(tuple(row.get(h, "").strip() for h in CSV_HEADERS))
        cur.executemany(insert_sql, batch)
        total += len(batch)
        print(f"  [{i:2d}/{len(files)}] {Path(f).name}: {len(batch):,} rows  (running total: {total:,})")
        if i % 10 == 0:
            con.commit()
    con.commit()
    print(f"\n  Total rows loaded: {total:,}  ({time.time()-t0:.1f}s)")

    # ── 2. Indexes on ownership ───────────────────────────────────────────────
    print("Creating ownership indexes...")
    cur.executescript("""
        CREATE INDEX idx_eid       ON ownership(enrollment_id);
        CREATE INDEX idx_aid       ON ownership(associate_id);
        CREATE INDEX idx_aid_owner ON ownership(associate_id_owner);
        CREATE INDEX idx_org       ON ownership(organization_name);
        CREATE INDEX idx_org_owner ON ownership(organization_name_owner);
        CREATE INDEX idx_state     ON ownership(state_owner);
    """)
    con.commit()

    # ── 3. facilities table (aggregated per facility) ─────────────────────────
    print("Building facilities table...")
    cur.executescript("""
        CREATE TABLE facilities AS
        WITH state_rank AS (
            SELECT enrollment_id,
                   state_owner,
                   ROW_NUMBER() OVER (
                       PARTITION BY enrollment_id
                       ORDER BY COUNT(*) DESC
                   ) AS rn
            FROM ownership
            WHERE state_owner != ''
            GROUP BY enrollment_id, state_owner
        ),
        best_state AS (
            SELECT enrollment_id, state_owner AS facility_state
            FROM state_rank WHERE rn = 1
        ),
        agg AS (
            SELECT
                enrollment_id,
                MAX(associate_id)        AS associate_id,
                MAX(organization_name)   AS organization_name,
                COUNT(DISTINCT associate_id_owner || '|' || COALESCE(role_code_owner, '')) AS owner_count,
                MAX(CASE WHEN llc_owner='Y'                   THEN 1 ELSE 0 END) AS has_llc,
                MAX(CASE WHEN corporation_owner='Y'           THEN 1 ELSE 0 END) AS has_corp,
                MAX(CASE WHEN private_equity_owner='Y'        THEN 1 ELSE 0 END) AS has_pe,
                MAX(CASE WHEN holding_company_owner='Y'       THEN 1 ELSE 0 END) AS has_holding,
                MAX(CASE WHEN investment_firm_owner='Y'       THEN 1 ELSE 0 END) AS has_investment,
                MAX(CASE WHEN non_profit_owner='Y'            THEN 1 ELSE 0 END) AS has_nonprofit,
                MAX(CASE WHEN reit_owner='Y'                  THEN 1 ELSE 0 END) AS has_reit,
                MAX(CASE WHEN trust_or_trustee_owner='Y'      THEN 1 ELSE 0 END) AS has_trust,
                MAX(CASE WHEN for_profit_owner='Y'            THEN 1 ELSE 0 END) AS has_forprofit,
                MAX(CASE WHEN chain_home_office_owner='Y'     THEN 1 ELSE 0 END) AS has_chain,
                MAX(CASE WHEN management_services_company='Y' THEN 1 ELSE 0 END) AS has_mgmt
            FROM ownership
            GROUP BY enrollment_id
        )
        SELECT
            agg.enrollment_id,
            agg.associate_id,
            agg.organization_name,
            COALESCE(bs.facility_state, '') AS facility_state,
            agg.owner_count,
            agg.has_llc, agg.has_corp, agg.has_pe, agg.has_holding,
            agg.has_investment, agg.has_nonprofit, agg.has_reit,
            agg.has_trust, agg.has_forprofit, agg.has_chain, agg.has_mgmt,
            RTRIM(
                CASE WHEN agg.has_llc=1        THEN 'LLC,'            ELSE '' END ||
                CASE WHEN agg.has_corp=1       THEN 'Corporation,'    ELSE '' END ||
                CASE WHEN agg.has_pe=1         THEN 'Private Equity,' ELSE '' END ||
                CASE WHEN agg.has_holding=1    THEN 'Holding Co.,'    ELSE '' END ||
                CASE WHEN agg.has_investment=1 THEN 'Investment Firm,' ELSE '' END ||
                CASE WHEN agg.has_nonprofit=1  THEN 'Non-Profit,'     ELSE '' END ||
                CASE WHEN agg.has_reit=1       THEN 'REIT,'           ELSE '' END ||
                CASE WHEN agg.has_trust=1      THEN 'Trust/Trustee,'  ELSE '' END ||
                CASE WHEN agg.has_forprofit=1  THEN 'For-Profit,'     ELSE '' END ||
                CASE WHEN agg.has_chain=1      THEN 'Chain Office,'   ELSE '' END ||
                CASE WHEN agg.has_mgmt=1       THEN 'Mgmt. Co.,'      ELSE '' END,
                ','
            ) AS owner_types
        FROM agg
        LEFT JOIN best_state bs USING (enrollment_id);
    """)
    con.commit()

    cur.executescript("""
        CREATE UNIQUE INDEX idx_fac_eid   ON facilities(enrollment_id);
        CREATE INDEX        idx_fac_state ON facilities(facility_state);
        CREATE INDEX        idx_fac_org   ON facilities(organization_name);
        CREATE INDEX        idx_fac_pe    ON facilities(has_pe);
        CREATE INDEX        idx_fac_llc   ON facilities(has_llc);
    """)
    con.commit()

    # ── 4. Full-text search index ─────────────────────────────────────────────
    print("Building full-text search index...")
    cur.executescript("""
        CREATE VIRTUAL TABLE fts_search USING fts5(
            enrollment_id UNINDEXED,
            organization_name,
            owner_full_name,
            owner_org_name,
            tokenize = 'unicode61'
        );

        INSERT INTO fts_search
            (enrollment_id, organization_name, owner_full_name, owner_org_name)
        SELECT DISTINCT
            enrollment_id,
            organization_name,
            TRIM(COALESCE(first_name_owner,'') || ' ' || COALESCE(last_name_owner,'')),
            COALESCE(organization_name_owner,'')
        FROM ownership;
    """)
    con.commit()

    # ── 5. Chain performance ───────────────────────────────────────────────────
    print("Loading chain performance data...")
    load_chain_performance(con)

    # ── 6. Summary ────────────────────────────────────────────────────────────
    row_count = cur.execute("SELECT COUNT(*) FROM ownership").fetchone()[0]
    fac_count = cur.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
    pe_count  = cur.execute("SELECT COUNT(*) FROM facilities WHERE has_pe=1").fetchone()[0]
    elapsed   = time.time() - t0

    print(f"""
Database built in {elapsed:.1f}s:
  Ownership rows : {row_count:,}
  Facilities     : {fac_count:,}
  PE-owned       : {pe_count:,}
  File           : {DB_PATH}
""")
    con.close()


def load_chain_performance(con):
    """Create and populate the chain_performance table from the CMS chain performance CSV."""
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chain_performance (
            chain_id TEXT PRIMARY KEY,
            chain_name TEXT,
            num_facilities INTEGER,
            num_states INTEGER,
            num_sff INTEGER,
            num_sff_candidates INTEGER,
            num_abuse_icon INTEGER,
            pct_abuse_icon REAL,
            pct_for_profit REAL,
            avg_overall_rating REAL,
            avg_health_rating REAL,
            avg_staffing_rating REAL,
            avg_quality_rating REAL,
            avg_nurse_hours REAL,
            avg_weekend_nurse_hours REAL,
            avg_rn_hours REAL,
            avg_nursing_turnover REAL,
            avg_rn_turnover REAL,
            avg_admin_turnover REAL,
            total_fines REAL,
            avg_fines REAL,
            total_penalties INTEGER,
            avg_rehospitalization REAL,
            avg_ed_visits REAL,
            avg_antipsychotic_shortstay REAL,
            avg_pressure_ulcers_shortstay REAL,
            avg_antipsychotic_longstay REAL,
            avg_falls REAL,
            avg_pressure_ulcers_longstay REAL,
            avg_uti REAL,
            avg_depression REAL,
            avg_weight_loss REAL,
            avg_preventable_readmissions REAL
        )
    """)
    con.commit()

    COL_MAP = [
        ("chain_name",                    "Chain"),
        ("num_facilities",                "Number of facilities"),
        ("num_states",                    "Number of states and territories with operations"),
        ("num_sff",                       "Number of Special Focus Facilities (SFF)"),
        ("num_sff_candidates",            "Number of SFF candidates"),
        ("num_abuse_icon",                "Number of facilities with an abuse icon"),
        ("pct_abuse_icon",                "Percentage of facilities with an abuse icon"),
        ("pct_for_profit",                "Percent of facilities classified as for-profit"),
        ("avg_overall_rating",            "Average overall 5-star rating"),
        ("avg_health_rating",             "Average health inspection rating"),
        ("avg_staffing_rating",           "Average staffing rating"),
        ("avg_quality_rating",            "Average quality rating"),
        ("avg_nurse_hours",               "Average total nurse hours per resident day"),
        ("avg_weekend_nurse_hours",       "Average total weekend nurse hours per resident day"),
        ("avg_rn_hours",                  "Average total Registered Nurse hours per resident day"),
        ("avg_nursing_turnover",          "Average total nursing staff turnover percentage"),
        ("avg_rn_turnover",               "Average Registered Nurse turnover percentage"),
        ("avg_admin_turnover",            "Average number of administrators who have left the nursing home"),
        ("total_fines",                   "Total amount of fines in dollars"),
        ("avg_fines",                     "Average amount of fines in dollars"),
        ("total_penalties",               "Total number of payment denials"),
        ("avg_rehospitalization",         "Average percentage of short-stay residents who were re-hospitalized after a nursing home admission"),
        ("avg_ed_visits",                 "Average percentage of short-stay residents who have had an outpatient emergency department visit"),
        ("avg_antipsychotic_shortstay",   "Average percentage of short-stay residents who newly received an antipsychotic medication"),
        ("avg_pressure_ulcers_shortstay", "Average percentage of short-stay residents with pressure ulcers or pressure injuries that are new or worsened"),
        ("avg_antipsychotic_longstay",    "Average percentage of long-stay residents who received an antipsychotic medication"),
        ("avg_falls",                     "Average percentage of long-stay residents experiencing one or more falls with major injury"),
        ("avg_pressure_ulcers_longstay",  "Average percentage of long-stay residents with pressure ulcers"),
        ("avg_uti",                       "Average percentage of long-stay residents with a urinary tract infection"),
        ("avg_depression",                "Average percentage of long-stay residents who have symptoms of depression"),
        ("avg_weight_loss",               "Average percentage of long-stay residents who lose too much weight"),
        ("avg_preventable_readmissions",  "Average rate of potentially preventable hospital readmissions 30 days after discharge from a SNF"),
    ]
    INT_COLS = {"num_facilities", "num_states", "num_sff", "num_sff_candidates", "num_abuse_icon", "total_penalties"}

    def to_float(v):
        if v is None or str(v).strip() == '':
            return None
        try:
            return float(str(v).strip().replace(',', ''))
        except Exception:
            return None

    def to_int(v):
        f = to_float(v)
        return int(f) if f is not None else None

    rows_loaded = 0
    with open(CHAIN_PERF_CSV, encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            chain_id = row.get('Chain ID', '').strip()
            if not chain_id:
                chain_id = 'NATIONAL'
            vals = {'chain_id': chain_id}
            for db_col, csv_col in COL_MAP:
                raw = row.get(csv_col, '').strip()
                if db_col in INT_COLS:
                    vals[db_col] = to_int(raw)
                elif db_col == 'chain_name':
                    vals[db_col] = raw or None
                else:
                    vals[db_col] = to_float(raw)
            cols = list(vals.keys())
            placeholders = ','.join(['?'] * len(cols))
            cur.execute(
                f"INSERT OR REPLACE INTO chain_performance ({','.join(cols)}) VALUES ({placeholders})",
                [vals[c] for c in cols]
            )
            rows_loaded += 1
    con.commit()
    print(f"  chain_performance: {rows_loaded} rows loaded")

    # NOTE: chain_id is added to the ratings table by a separate patch script
    # (see Step 1 of the chain performance integration). The ratings table is
    # loaded outside of build_db.py and chain_id is populated via UPDATE by CCN.


if __name__ == "__main__":
    build()
