from __future__ import annotations

import json
import secrets
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                nome_cliente TEXT,
                nome_empresa TEXT,
                input_json TEXT NOT NULL,
                output_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                auth_user TEXT NOT NULL,
                idem_key TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (auth_user, idem_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                login TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'analista',
                created_at TEXT NOT NULL
            )
            """
        )
        cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "role" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'analista'")
        conn.execute("UPDATE users SET role = 'analista' WHERE role IS NULL OR role = ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sim_created_at ON simulations(created_at DESC)")
        conn.commit()


def save_simulation(db_path: Path, record: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO simulations
            (id, created_at, nome_cliente, nome_empresa, input_json, output_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["created_at"],
                record.get("nome_cliente"),
                record.get("nome_empresa"),
                json.dumps(record.get("input") or {}, ensure_ascii=False),
                json.dumps(record.get("output") or {}, ensure_ascii=False),
            ),
        )
        conn.commit()


def get_simulation(db_path: Path, sim_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, created_at, nome_cliente, nome_empresa, input_json, output_json
            FROM simulations
            WHERE id = ?
            """,
            (sim_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "created_at": row[1],
        "nome_cliente": row[2],
        "nome_empresa": row[3],
        "input": json.loads(row[4]),
        "output": json.loads(row[5]),
    }


def list_simulations(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, nome_cliente, nome_empresa, input_json, output_json
            FROM simulations
            ORDER BY created_at DESC
            """
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "id": row[0],
                "created_at": row[1],
                "nome_cliente": row[2],
                "nome_empresa": row[3],
                "input": json.loads(row[4]),
                "output": json.loads(row[5]),
            }
        )
    return records


def delete_simulation(db_path: Path, sim_id: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM simulations WHERE id = ?", (sim_id,))
        conn.commit()


def set_idempotency(db_path: Path, auth_user: str, idem_key: str, sim_id: str) -> None:
    now = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO idempotency_keys
            (auth_user, idem_key, simulation_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (auth_user, idem_key, sim_id, now),
        )
        conn.commit()


def get_idempotency(db_path: Path, auth_user: str, idem_key: str) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT simulation_id
            FROM idempotency_keys
            WHERE auth_user = ? AND idem_key = ?
            """,
            (auth_user, idem_key),
        ).fetchone()
    if not row:
        return None
    return str(row[0])


def migrate_legacy_json_simulations(db_path: Path, simulations_dir: Path) -> int:
    if not simulations_dir.exists():
        return 0
    migrated = 0
    for path in simulations_dir.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        sim_id = payload.get("id")
        created_at = payload.get("created_at")
        if not sim_id or not created_at:
            continue
        record = {
            "id": sim_id,
            "created_at": created_at,
            "nome_cliente": payload.get("nome_cliente"),
            "nome_empresa": payload.get("nome_empresa"),
            "input": payload.get("input") or {},
            "output": payload.get("output") or {},
        }
        save_simulation(db_path, record)
        migrated += 1
    return migrated


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt, digest_hex = encoded.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return secrets.compare_digest(digest.hex(), digest_hex)


def ensure_default_user(db_path: Path, login: str, password: str) -> None:
    now = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(1) FROM users").fetchone()
        total = int(row[0]) if row else 0
        if total > 0:
            return
        conn.execute(
            "INSERT INTO users (login, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (login, hash_password(password), "admin", now),
        )
        conn.commit()


def list_users(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT login, role, created_at FROM users ORDER BY login ASC").fetchall()
    return [{"login": row[0], "role": row[1], "created_at": row[2]} for row in rows]


def get_user(db_path: Path, login: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT login, password_hash, role, created_at FROM users WHERE login = ?",
            (login,),
        ).fetchone()
    if not row:
        return None
    return {"login": row[0], "password_hash": row[1], "role": row[2], "created_at": row[3]}


def authenticate_user(db_path: Path, login: str, password: str) -> bool:
    user = get_user(db_path, login)
    if not user:
        return False
    return verify_password(password, str(user["password_hash"]))


def create_user(db_path: Path, login: str, password: str, role: str = "analista") -> None:
    now = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (login, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (login, hash_password(password), role, now),
        )
        conn.commit()


def update_user_password(db_path: Path, login: str, password: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE login = ?",
            (hash_password(password), login),
        )
        conn.commit()
    return cursor.rowcount > 0


def delete_user(db_path: Path, login: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM users WHERE login = ?", (login,))
        conn.commit()
    return cursor.rowcount > 0


def count_users(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(1) FROM users").fetchone()
    return int(row[0]) if row else 0


def set_user_role(db_path: Path, login: str, role: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("UPDATE users SET role = ? WHERE login = ?", (role, login))
        conn.commit()
    return cursor.rowcount > 0
