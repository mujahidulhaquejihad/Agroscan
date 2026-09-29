"""Lightweight SQLite user store + session tokens."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "users.db"
SESSION_DAYS = 30           # one session is 30 days##


def _connect():             ###    This function establishes a connection to the SQLite database located at DB_PATH.##
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _ensure_delivery_columns(con: sqlite3.Connection) -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}           ####    We are making sure that the users table has the necessary columns
                                                                                        ####for delivery information and active status. If any of these columns are missing,
                                                                                        #### we will add them to the table.####
    for name, decl in (
        ("phone", "TEXT"),
        ("address", "TEXT"),
        ("district", "TEXT"),
        ("upazila", "TEXT"),
        ("active", "INTEGER DEFAULT 1"),
    ):
        if name not in cols:
            con.execute(f"ALTER TABLE users ADD COLUMN {name} {decl}")
    # Backfill active for older rows
    if "active" not in cols:
        con.execute("UPDATE users SET active = 1 WHERE active IS NULL")


def init_db():          ###    This function initializes the database by creating the necessary tables if they do not already exist. ###
                        ##It creates a users table to store user information and a sessions table to manage user sessions. ###
                        # ##Additionally, it ensures that the users table has the required columns for delivery information##
                        # ## and active status. Finally, it commits the changes to the database.####
    with _connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT,
                provider TEXT NOT NULL DEFAULT 'local',
                picture TEXT,
                google_sub TEXT UNIQUE,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        _ensure_delivery_columns(con)
        con.commit()


def _hash_password(password: str) -> str:           #Generates a unique 16-byte cryptographically secure random hexadecimal string as a salt.##
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return secrets.compare_digest(check.hex(), digest)


def _user_dict(row: sqlite3.Row, *, admin: bool = False, active_sessions: int | None = None) -> dict:
    keys = set(row.keys())
    out = {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "provider": row["provider"],
        "picture": row["picture"],
        "phone": (row["phone"] or "") if "phone" in keys else "",
        "address": (row["address"] or "") if "address" in keys else "",
        "district": (row["district"] or "") if "district" in keys else "",
        "upazila": (row["upazila"] or "") if "upazila" in keys else "",
        "active": int(row["active"]) if "active" in keys and row["active"] is not None else 1,
    }
    if admin:
        out["created_at"] = row["created_at"] if "created_at" in keys else ""
        if active_sessions is not None:
            out["active_sessions"] = int(active_sessions)
        else:
            out["active_sessions"] = 0
    return out


def _session_counts(con: sqlite3.Connection, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" for _ in user_ids)
    rows = con.execute(
        f"""
        SELECT user_id, COUNT(*) AS c FROM sessions
        WHERE user_id IN ({placeholders}) AND expires_at > ?
        GROUP BY user_id
        """,
        [*user_ids, now],
    ).fetchall()
    return {int(r["user_id"]): int(r["c"]) for r in rows}


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()


def create_local_user(
    name: str,
    email: str,
    password: str,
    *,
    phone: str = "",
    address: str = "",
    district: str = "",
    upazila: str = "",
) -> dict:
    init_db()
    email = email.strip().lower()
    with _connect() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("Email already registered")
        cur = con.execute(
            """
            INSERT INTO users (
                email, name, password_hash, provider, created_at,
                phone, address, district, upazila
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                email,
                name.strip(),
                _hash_password(password),
                "local",
                datetime.now(timezone.utc).isoformat(),
                (phone or "").strip(),
                (address or "").strip(),
                (district or "").strip(),
                (upazila or "").strip(),
            ),
        )
        user_id = cur.lastrowid
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_dict(row)


def login_local(email: str, password: str) -> dict:
    init_db()
    email = email.strip().lower()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE email=? AND provider='local'", (email,)).fetchone()
        if not row or not row["password_hash"] or not _check_password(password, row["password_hash"]):
            raise ValueError("Invalid email or password")
        keys = set(row.keys())
        if "active" in keys and row["active"] is not None and int(row["active"]) == 0:
            raise ValueError("Account is disabled. Contact support.")
    return _user_dict(row)


def get_user_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    init_db()
    with _connect() as con:
        row = con.execute(
            """
            SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND s.expires_at > ?
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    if not row:
        return None
    keys = set(row.keys())
    if "active" in keys and row["active"] is not None and int(row["active"]) == 0:
        return None
    return _user_dict(row)


def upsert_google_user(name: str, email: str, picture: str, google_sub: str) -> dict:
    init_db()
    email = (email or f"{google_sub}@google.local").strip().lower()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone()
        if row:
            con.execute(
                "UPDATE users SET name=?, email=?, picture=? WHERE id=?",
                (name, email, picture, row["id"]),
            )
            user_id = row["id"]
        else:
            cur = con.execute(
                "INSERT INTO users (email,name,provider,picture,google_sub,created_at) VALUES (?,?,?,?,?,?)",
                (email, name, "google", picture, google_sub, datetime.now(timezone.utc).isoformat()),
            )
            user_id = cur.lastrowid
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_dict(row)


def create_session(user_id: int) -> str:
    token = _new_token()
    with _connect() as con:
        con.execute(
            "INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)",
            (token, user_id, _expires_at()),
        )
        con.commit()
    return token


def delete_session(token: str):
    if not token:
        return
    with _connect() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()

####User Profile Management###
def update_user_profile(
    user_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    district: str | None = None,
    upazila: str | None = None,
) -> dict:
    init_db()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("User not found")
        keys = set(row.keys())

        def _cur(field: str) -> str:
            return (row[field] or "") if field in keys else ""

        next_name = name.strip() if name is not None else row["name"]
        next_phone = phone.strip() if phone is not None else _cur("phone")
        next_address = address.strip() if address is not None else _cur("address")
        next_district = district.strip() if district is not None else _cur("district")
        next_upazila = upazila.strip() if upazila is not None else _cur("upazila")
        if not next_name:
            raise ValueError("Name is required")
        con.execute(
            """
            UPDATE users
            SET name=?, phone=?, address=?, district=?, upazila=?
            WHERE id=?
            """,
            (next_name, next_phone, next_address, next_district, next_upazila, user_id),
        )
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_dict(row)

###Admin Dashboard Functions####
def admin_list_users(search: str = "", limit: int = 100, offset: int = 0) -> dict:
    init_db()
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    q = "SELECT * FROM users WHERE 1=1"
    params: list = []
    if search:
        like = f"%{search.strip()}%"
        q += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ? OR district LIKE ? OR upazila LIKE ?)"
        params.extend([like, like, like, like, like])
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as con:
        rows = con.execute(q, params).fetchall()
        total = con.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        counts = _session_counts(con, [int(r["id"]) for r in rows])
    return {
        "users": [
            _user_dict(r, admin=True, active_sessions=counts.get(int(r["id"]), 0))
            for r in rows
        ],
        "total": int(total),
    }


def admin_get_user(user_id: int) -> dict:
    init_db()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("User not found")
        counts = _session_counts(con, [user_id])
    return _user_dict(row, admin=True, active_sessions=counts.get(user_id, 0))


def admin_update_user(
    user_id: int,
    *,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    district: str | None = None,
    upazila: str | None = None,
    active: int | None = None,
    password: str | None = None,
) -> dict:
    init_db()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("User not found")
        keys = set(row.keys())

        def _cur(field: str) -> str:
            return (row[field] or "") if field in keys else ""

        next_name = name.strip() if name is not None else row["name"]
        next_email = email.strip().lower() if email is not None else (row["email"] or "")
        next_phone = phone.strip() if phone is not None else _cur("phone")
        next_address = address.strip() if address is not None else _cur("address")
        next_district = district.strip() if district is not None else _cur("district")
        next_upazila = upazila.strip() if upazila is not None else _cur("upazila")
        next_active = int(active) if active is not None else (
            int(row["active"]) if "active" in keys and row["active"] is not None else 1
        )
        if not next_name:
            raise ValueError("Name is required")
        if next_email:
            clash = con.execute(
                "SELECT id FROM users WHERE email=? AND id!=?",
                (next_email, user_id),
            ).fetchone()
            if clash:
                raise ValueError("Email already in use by another account")

        if password is not None and password.strip():
            if len(password.strip()) < 6:
                raise ValueError("Password must be at least 6 characters")
            con.execute(
                """
                UPDATE users
                SET name=?, email=?, phone=?, address=?, district=?, upazila=?, active=?, password_hash=?
                WHERE id=?
                """,
                (
                    next_name,
                    next_email,
                    next_phone,
                    next_address,
                    next_district,
                    next_upazila,
                    next_active,
                    _hash_password(password.strip()),
                    user_id,
                ),
            )
        else:
            con.execute(
                """
                UPDATE users
                SET name=?, email=?, phone=?, address=?, district=?, upazila=?, active=?
                WHERE id=?
                """,
                (
                    next_name,
                    next_email,
                    next_phone,
                    next_address,
                    next_district,
                    next_upazila,
                    next_active,
                    user_id,
                ),
            )
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        counts = _session_counts(con, [user_id])
    return _user_dict(row, admin=True, active_sessions=counts.get(user_id, 0))


def admin_revoke_user_sessions(user_id: int) -> int:
    init_db()
    with _connect() as con:
        cur = con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        con.commit()
        return cur.rowcount or 0


def admin_delete_user(user_id: int) -> None:
    init_db()
    with _connect() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("User not found")
        con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM users WHERE id=?", (user_id,))
        con.commit()

####Gathers high-level system metrics for dashboard summaries###
def admin_user_stats() -> dict:
    init_db()
    with _connect() as con:
        total = con.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        active = con.execute(
            "SELECT COUNT(*) AS c FROM users WHERE COALESCE(active,1)=1"
        ).fetchone()["c"]
        local = con.execute(
            "SELECT COUNT(*) AS c FROM users WHERE provider='local'"
        ).fetchone()["c"]
        google = con.execute(
            "SELECT COUNT(*) AS c FROM users WHERE provider='google'"
        ).fetchone()["c"]
        sessions = con.execute(
            "SELECT COUNT(*) AS c FROM sessions WHERE expires_at > ?",
            (datetime.now(timezone.utc).isoformat(),),
        ).fetchone()["c"]
    return {
        "users_total": int(total),
        "users_active": int(active),
        "users_local": int(local),
        "users_google": int(google),
        "sessions_active": int(sessions),
    }
