from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from uuid import uuid4

DATABASE_PATH = Path(__file__).resolve().parent / "data" / "CampusFind.db"

DEFAULT_LOCATIONS = (
    "Cafeteria",
    "Room 1",
    "Room 2",
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "assets" / "images"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def create_connection() -> sqlite3.Connection:
    """Create and return a connection to the SQLite database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL
                    CHECK (report_type IN ('LOST', 'FOUND')),
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                color TEXT NOT NULL,
                location TEXT NOT NULL,
                event_date TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                status TEXT NOT NULL DEFAULT 'Open'
                    CHECK (status IN ('Open', 'Claim Pending', 'Returned')),
                created_at TEXT NOT NULL DEFAULT
                CURRENT_TIMESTAMP
            )
            """
        )

        columns = connection.execute("PRAGMA table_info(items)").fetchall()

        column_names = {str(column["name"]).lower() for column in columns}

        if "image_path" not in column_names:
            connection.execute("ALTER TABLE items ADD COLUMN image_path TEXT")

        if "event_date" not in column_names:
            connection.execute(
                "ALTER TABLE items ADD COLUMN event_date TEXT NOT NULL DEFAULT ''"
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                contact TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
            """
        )
            
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE
                    CHECK (length(trim(name)) > 0)
            )
            """
        )

        has_locations = connection.execute(
            "SELECT 1 FROM locations LIMIT 1"
        ).fetchone()

        if has_locations is None:
            for location in DEFAULT_LOCATIONS:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO locations (name)
                    VALUES (?)
                    """,
                    (location,),
                )
                
        connection.commit()

    migrate_claim_status()


def add_item(
    report_type: str,
    item_name: str,
    category: str,
    color: str,
    location: str,
    event_date: date,
    description: str,
    image_path: str | None,
) -> int:
    """Insert an item report and return its database ID."""
    with closing(create_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO items (
                report_type,
                item_name,
                category,
                color,
                location,
                event_date,
                description,
                image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_type,
                item_name.strip(),
                category,
                color.strip(),
                location.strip(),
                event_date.isoformat(),
                description.strip(),
                image_path,
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError("The report was not saved correctly.")

        return int(cursor.lastrowid)


def get_all_items() -> list[dict[str, object]]:
    """Return all reports, newest first."""
    with closing(create_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                report_type,
                item_name,
                category,
                color,
                location,
                event_date AS event_date,
                description,
                image_path,
                status,
                created_at
            FROM items
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def delete_item(item_id: int) -> None:
    """Delete a report by its ID."""
    with closing(create_connection()) as connection:
        connection.execute(
            "DELETE FROM items WHERE id = ?",
            (item_id,),
        )
        connection.commit()


def save_claim_info(
    item_id: int,
    name: str,
    email: str,
    contact: str,
) -> bool:
    """Save a claim and change status together."""
    with closing(create_connection()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE items
            SET status = 'Claim Pending'
            WHERE id = ?
              AND report_type = 'FOUND'
              AND status = 'Open'
              AND NOT EXISTS (
                  SELECT 1 FROM claims WHERE item_id = items.id
              )
            """,
            (item_id,),
        )

        if cursor.rowcount != 1:
            return False

        connection.execute(
            """
            INSERT INTO claims (item_id, name, email, contact)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, name.strip(), email.strip(), contact.strip()),
        )

    return True


def save_uploaded_photo(uploaded_file):
    """Save the uploaded photo to the database."""
    if uploaded_file is None:
        return None

    extension = Path(uploaded_file.name).suffix.lower()
    new_filename = f"{uuid4().hex}{extension}"
    image_path = UPLOAD_DIR / new_filename

    image_path.write_bytes(uploaded_file.getvalue())

    return str(image_path)


def get_item_by_id(item_id: int) -> dict | None:
    """Return one item, or None if it no longer exists."""
    with closing(create_connection()) as connection:
        row = connection.execute(
            "SELECT * FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def migrate_claim_status() -> None:
    """Update the old items table without losing reports."""
    with closing(create_connection()) as connection, connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")

        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'items'"
        ).fetchone()[0]

        if "Claim Pending" in schema:
            return

        old_sequence = connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'items'"
        ).fetchone()

        connection.execute(
            """
            CREATE TABLE items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL
                    CHECK (report_type IN ('LOST', 'FOUND')),
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                color TEXT NOT NULL,
                location TEXT NOT NULL,
                event_date TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                status TEXT NOT NULL DEFAULT 'Open'
                    CHECK (status IN ('Open', 'Claim Pending', 'Returned')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            INSERT INTO items_new (
                id, report_type, item_name, category, color, location,
                event_date, description, image_path, status, created_at
            )
            SELECT
                id, report_type, item_name, category, color, location,
                event_date, description, image_path,
                CASE
                    WHEN status = 'Matched' THEN 'Claim Pending'
                    WHEN status = 'Open' AND report_type = 'FOUND'
                         AND EXISTS (
                             SELECT 1 FROM claims WHERE item_id = items.id
                         )
                    THEN 'Claim Pending'
                    ELSE status
                END,
                created_at
            FROM items
            """
        )

        connection.execute("DROP TABLE items")
        connection.execute("ALTER TABLE items_new RENAME TO items")

        if old_sequence is not None:
            connection.execute(
                "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'items'",
                (old_sequence[0],),
            )

        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("Migration failed: invalid claim references.")

def mark_item_returned(item_id: int) -> bool:
    """Mark a pending Found item as Returned."""
    with closing(create_connection()) as connection:
        cursor = connection.execute(
            """
            UPDATE items
            SET status = 'Returned'
            WHERE id = ?
              AND report_type = 'FOUND'
              AND status = 'Claim Pending'
            """,
            (item_id,),
        )
        connection.commit()

        return cursor.rowcount == 1

def get_claims_for_item(item_id: int) -> list[dict]:
    """Return claims for one item."""
    with closing(create_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, name, email, contact, created_at
            FROM claims
            WHERE item_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (item_id,),
        ).fetchall()

    return [dict(row) for row in rows]

def get_locations() -> list[str]:
    """Return all available locations."""
    with closing(create_connection()) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM locations
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

    return [row["name"] for row in rows]


def add_location(name: str) -> bool:
    """Add a new location. Return False if it already exists."""
    name = name.strip()

    if not name:
        return False

    with closing(create_connection()) as connection:
        existing = connection.execute(
            """
            SELECT 1
            FROM locations
            WHERE LOWER(name) = LOWER(?)
            """,
            (name,),
        ).fetchone()

        if existing:
            return False

        connection.execute(
            """
            INSERT INTO locations (name)
            VALUES (?)
            """,
            (name,),
        )
        connection.commit()

    return True


def delete_location(name: str) -> bool:
    """Delete a location from future report options."""
    with closing(create_connection()) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM locations"
        ).fetchone()[0]

        if count <= 1:
            return False

        cursor = connection.execute(
            """
            DELETE FROM locations
            WHERE name = ?
            """,
            (name,),
        )

        connection.commit()

    return cursor.rowcount == 1


def seed_demo_data() -> bool:
    """Seed a brand-new/empty SQLite DB with sample Lost & Found reports.

    Existing reports are never modified. Demo photo must be kept in
    assets/demo/airpods.jpg (a version-controlled folder).
    Returns True if two demo reports were inserted.
    """
    demo_photo = BASE_DIR / "assets" / "demo" / "airpods.jpg"
    photo_path = str(demo_photo) if demo_photo.is_file() else None
    today = date.today().isoformat()

    with closing(create_connection()) as connection, connection:
        # A transaction avoids adding only half the demo pair.
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM items LIMIT 1").fetchone():
            return False

        connection.executemany(
            """
            INSERT INTO items (
                report_type, item_name, category, color, location,
                event_date, description, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "FOUND", "AirPods Pro", "Electronics", "White",
                    "Cafeteria", today,
                    "DEMO REPORT: White AirPods Pro found in the cafeteria.",
                    photo_path,
                ),
                (
                    "LOST", "AirPods Pro", "Electronics", "White",
                    "Cafeteria", today,
                    "DEMO REPORT: Lost my white AirPods Pro in the cafeteria.",
                    None,
                ),
            ],
        )
        return True