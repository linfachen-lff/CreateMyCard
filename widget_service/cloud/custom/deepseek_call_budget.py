"""Persistent cross-process DeepSeek call budget with atomic pre-call reservation."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


class DeepSeekCallBudgetExceeded(RuntimeError):
    """Raised before transport invocation when the configured limit is exhausted."""


@dataclass(frozen=True)
class DeepSeekBudgetStatus:
    used: int
    remaining: int | None
    limit: int | None


class DeepSeekCallBudget:
    """Reserve every physical DeepSeek attempt under one durable SQLite counter."""

    DEFAULT_LIMIT = 400

    def __init__(self, path: Path, limit: int = DEFAULT_LIMIT) -> None:
        if limit < 0:
            raise ValueError("DeepSeek call budget limit cannot be negative")
        self.path = path
        self.limit = limit or None

    def reserve(self, provider: str) -> DeepSeekBudgetStatus:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS budget "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), used INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS attempts "
                "(sequence INTEGER PRIMARY KEY, reserved_at_ms INTEGER NOT NULL, "
                "provider TEXT NOT NULL)"
            )
            connection.execute("INSERT OR IGNORE INTO budget(id, used) VALUES (1, 0)")
            used = int(connection.execute("SELECT used FROM budget WHERE id = 1").fetchone()[0])
            if self.limit is not None and used >= self.limit:
                connection.execute("ROLLBACK")
                raise DeepSeekCallBudgetExceeded(
                    f"DeepSeek call budget exhausted: used={used}, limit={self.limit}"
                )
            reserved = used + 1
            connection.execute("UPDATE budget SET used = ? WHERE id = 1", (reserved,))
            connection.execute(
                "INSERT INTO attempts(sequence, reserved_at_ms, provider) VALUES (?, ?, ?)",
                (reserved, int(time.time() * 1000), provider),
            )
            connection.execute("COMMIT")
            return DeepSeekBudgetStatus(
                used=reserved,
                remaining=None if self.limit is None else self.limit - reserved,
                limit=self.limit,
            )
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def status(self) -> DeepSeekBudgetStatus:
        if not self.path.is_file():
            return DeepSeekBudgetStatus(used=0, remaining=self.limit, limit=self.limit)
        connection = sqlite3.connect(self.path, timeout=30.0)
        try:
            row = connection.execute("SELECT used FROM budget WHERE id = 1").fetchone()
        except sqlite3.OperationalError:
            row = None
        finally:
            connection.close()
        used = int(row[0]) if row else 0
        return DeepSeekBudgetStatus(
            used=used,
            remaining=None if self.limit is None else max(0, self.limit - used),
            limit=self.limit,
        )
