"""DAO boundary for runtime templates and source descriptions."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from api_schema import JSONObject

from .errors import (
    InvalidSearchRequest,
    ObservedShapeError,
    PayloadLimitError,
    TemplateStoreError,
)
from .hashing import SIGNATURE_VERSION, PayloadLimits, compute_shape_signature
from .json_boundary import loads_strict_json
from .tokenization import token_index_text


@dataclass(frozen=True)
class TemplateRecord:
    template_id: str
    description: str
    tags: tuple[str, ...]
    reference_jsonl: str
    input_json: str
    structure_hash: str
    signature_version: int = SIGNATURE_VERSION
    # LOCAL PATCH: 卡片尺寸（如 "2x2"），structure 匹配时按尺寸过滤（见 VENDORED.md P2）
    size: str | None = None


@dataclass(frozen=True)
class KeywordCandidate:
    template: TemplateRecord
    bm25_score: float


@dataclass(frozen=True)
class SignatureRebuildReport:
    updated_template_ids: tuple[str, ...]
    rejected: tuple[tuple[str, str, str | None], ...]


@dataclass(frozen=True)
class DescriptionRecord:
    description: str
    tags: tuple[str, ...]


class SearchTemplateDAO(Protocol):
    """Narrow read contract consumed by online Search."""

    def find_by_signature(
        self, signature: str, version: int
    ) -> list[TemplateRecord]: ...

    def keyword_candidates(
        self, tokens: list[str], limit: int
    ) -> list[KeywordCandidate]: ...


class TemplateDAO(SearchTemplateDAO, Protocol):
    """Management contract for importing and maintaining runtime templates."""

    def initialize(self) -> None: ...

    def count(self) -> int: ...

    def upsert(self, record: TemplateRecord) -> None: ...

    def replace_all(self, records: list[TemplateRecord]) -> None: ...

    def delete_all(self) -> None: ...

    def list_all(self) -> list[TemplateRecord]: ...

    def rebuild_signatures(
        self, limits: PayloadLimits | None = None
    ) -> SignatureRebuildReport: ...


class DescriptionDAO(Protocol):
    """Read-only metadata contract used during cards import."""

    def find(self, title: str, input_data: JSONObject) -> DescriptionRecord | None: ...


class SQLiteTemplateDAO:
    """SQLite implementation; every user value is passed as a SQL parameter."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_connection: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._memory_connection = self._connect()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._memory_connection or self._connect()
            yield connection
        except sqlite3.Error as exc:
            raise TemplateStoreError(
                "store_unavailable", "template database operation failed"
            ) from exc
        finally:
            if connection is not None and self._memory_connection is None:
                connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS templates (
                    template_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    reference_jsonl TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    structure_hash TEXT NOT NULL,
                    signature_version INTEGER NOT NULL,
                    indexed_text TEXT NOT NULL,
                    size TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS templates_structure_signature
                    ON templates(structure_hash, signature_version);
                CREATE VIRTUAL TABLE IF NOT EXISTS templates_fts USING fts5(
                    template_id UNINDEXED,
                    indexed_text,
                    tokenize='unicode61'
                );
                """
            )
            connection.execute(
                """
                INSERT INTO search_metadata(key, value)
                VALUES ('signature_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(SIGNATURE_VERSION),),
            )
            connection.commit()

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT count(*) AS count FROM templates"
            ).fetchone()
            return int(row["count"] if row is not None else 0)

    def upsert(self, record: TemplateRecord) -> None:
        with self._connection() as connection, connection:
            self._upsert_on_connection(connection, record)

    def replace_all(self, records: list[TemplateRecord]) -> None:
        """Replace templates and FTS rows in one transaction."""

        with self._connection() as connection, connection:
            connection.execute("DELETE FROM templates")
            connection.execute("DELETE FROM templates_fts")
            for record in records:
                self._upsert_on_connection(connection, record)

    @staticmethod
    def _upsert_on_connection(
        connection: sqlite3.Connection, record: TemplateRecord
    ) -> None:
        indexed_text = token_index_text(record.description, record.tags)
        connection.execute(
            """
                    INSERT INTO templates(
                        template_id, description, tags_json, reference_jsonl,
                        input_json, structure_hash, signature_version, indexed_text,
                        size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(template_id) DO UPDATE SET
                        description=excluded.description,
                        tags_json=excluded.tags_json,
                        reference_jsonl=excluded.reference_jsonl,
                        input_json=excluded.input_json,
                        structure_hash=excluded.structure_hash,
                        signature_version=excluded.signature_version,
                        indexed_text=excluded.indexed_text,
                        size=excluded.size
                    """,
            (
                record.template_id,
                record.description,
                json.dumps(record.tags, ensure_ascii=False),
                record.reference_jsonl,
                record.input_json,
                record.structure_hash,
                record.signature_version,
                indexed_text,
                record.size or "",
            ),
        )
        connection.execute(
            "DELETE FROM templates_fts WHERE template_id = ?",
            (record.template_id,),
        )
        connection.execute(
            "INSERT INTO templates_fts(template_id, indexed_text) VALUES (?, ?)",
            (record.template_id, indexed_text),
        )

    def delete_all(self) -> None:
        with self._connection() as connection, connection:
            connection.execute("DELETE FROM templates")
            connection.execute("DELETE FROM templates_fts")

    def find_by_signature(self, signature: str, version: int) -> list[TemplateRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM templates
                WHERE structure_hash = ? AND signature_version = ?
                ORDER BY template_id
                """,
                (signature, version),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def list_all(self) -> list[TemplateRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM templates ORDER BY template_id"
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def keyword_candidates(
        self, tokens: list[str], limit: int
    ) -> list[KeywordCandidate]:
        if not tokens or limit <= 0:
            return []
        query = " OR ".join(
            f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens
        )
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT t.*, bm25(templates_fts) AS bm25_score
                FROM templates_fts
                JOIN templates AS t USING(template_id)
                WHERE templates_fts MATCH ?
                ORDER BY bm25_score ASC, t.template_id ASC
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [
            KeywordCandidate(self._record_from_row(row), float(row["bm25_score"]))
            for row in rows
        ]

    def rebuild_signatures(
        self, limits: PayloadLimits | None = None
    ) -> SignatureRebuildReport:
        updated: list[str] = []
        rejected: list[tuple[str, str, str | None]] = []
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT template_id, input_json FROM templates ORDER BY template_id"
            ).fetchall()
            replacements: list[tuple[str, int, str]] = []
            for row in rows:
                template_id = str(row["template_id"])
                try:
                    payload = loads_strict_json(str(row["input_json"]))
                    if not isinstance(payload, dict):
                        raise InvalidSearchRequest(
                            "invalid_input_json",
                            "stored template input must be a JSON object",
                        )
                    signature = compute_shape_signature(payload, limits)
                except (
                    InvalidSearchRequest,
                    ObservedShapeError,
                    PayloadLimitError,
                ) as exc:
                    rejected.append(
                        (
                            template_id,
                            getattr(exc, "code", "invalid_input_json"),
                            getattr(exc, "pointer", None),
                        )
                    )
                    continue
                replacements.append(
                    (signature.signature, signature.version, template_id)
                )
                updated.append(template_id)
            with connection:
                connection.executemany(
                    """
                    UPDATE templates
                    SET structure_hash = ?, signature_version = ?
                    WHERE template_id = ?
                    """,
                    replacements,
                )
                connection.execute(
                    """
                    INSERT INTO search_metadata(key, value)
                    VALUES ('signature_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (str(SIGNATURE_VERSION),),
                )
        return SignatureRebuildReport(tuple(updated), tuple(rejected))

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> TemplateRecord:
        try:
            tags = json.loads(str(row["tags_json"]))
        except json.JSONDecodeError as exc:
            raise TemplateStoreError(
                "invalid_template_record", "template tags are not valid JSON"
            ) from exc
        if not isinstance(tags, list):
            raise TemplateStoreError(
                "invalid_template_record", "template tags must be a JSON array"
            )
        return TemplateRecord(
            template_id=str(row["template_id"]),
            description=str(row["description"]),
            tags=tuple(str(tag) for tag in tags),
            reference_jsonl=str(row["reference_jsonl"]),
            input_json=str(row["input_json"]),
            structure_hash=str(row["structure_hash"]),
            signature_version=int(row["signature_version"]),
            size=str(row["size"]) if row["size"] else None,
        )


class SQLiteDescriptionDAO:
    """Read LLM-generated descriptions and tags from an existing database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            uri = f"{self.path.as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            yield connection
        except sqlite3.Error as exc:
            raise TemplateStoreError(
                "description_store_unavailable",
                "description database operation failed",
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    def find(self, title: str, input_data: JSONObject) -> DescriptionRecord | None:
        with self._connection() as connection:
            exact = connection.execute(
                """
                SELECT description, tags_json
                FROM templates
                WHERE enabled = ? AND title = ?
                ORDER BY template_id
                """,
                (1, title),
            ).fetchall()
            if len(exact) == 1:
                return self._description_from_row(exact[0])
            if len(exact) > 1:
                return None

            # One historical card has a renamed title. Compare parsed examples in
            # Python instead of interpolating JSON into SQL or depending on JSON1.
            rows = connection.execute(
                """
                SELECT description, tags_json, data_example_json
                FROM templates
                WHERE enabled = ?
                ORDER BY template_id
                """,
                (1,),
            ).fetchall()
        matches: list[DescriptionRecord] = []
        for row in rows:
            try:
                example = json.loads(str(row["data_example_json"]))
            except json.JSONDecodeError:
                continue
            if example == input_data:
                matches.append(self._description_from_row(row))
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _description_from_row(row: sqlite3.Row) -> DescriptionRecord:
        description = str(row["description"]).strip()
        try:
            raw_tags = json.loads(str(row["tags_json"]))
        except json.JSONDecodeError as exc:
            raise TemplateStoreError(
                "invalid_description_metadata",
                "description tags are not valid JSON",
            ) from exc
        if not description or not isinstance(raw_tags, list):
            raise TemplateStoreError(
                "invalid_description_metadata",
                "description metadata must contain text and a tags array",
            )
        return DescriptionRecord(
            description=description,
            tags=tuple(str(tag).strip() for tag in raw_tags if str(tag).strip()),
        )
