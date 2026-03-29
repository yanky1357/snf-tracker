#!/usr/bin/env python3
"""Build the SQLite database for NourishNY applications."""

import sqlite3
import os

DB_PATH = os.environ.get('DB_PATH', 'nourishny.db')


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            medicaid_id TEXT NOT NULL,
            cell_phone TEXT NOT NULL,
            home_phone TEXT,
            email TEXT NOT NULL,
            street_address TEXT NOT NULL,
            apt_unit TEXT,
            city TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'NY',
            zipcode TEXT NOT NULL,
            health_categories TEXT,
            is_employed TEXT NOT NULL,
            spouse_employed TEXT NOT NULL,
            has_wic TEXT NOT NULL,
            has_snap TEXT NOT NULL,
            food_allergies TEXT,
            is_new_applicant TEXT NOT NULL,
            household_members TEXT,
            status TEXT DEFAULT 'new',
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('CREATE INDEX idx_status ON applications(status)')
    c.execute('CREATE INDEX idx_created ON applications(created_at)')
    c.execute('CREATE INDEX idx_medicaid ON applications(medicaid_id)')

    conn.commit()
    conn.close()
    print(f'Database created at {DB_PATH}')


if __name__ == '__main__':
    build()
