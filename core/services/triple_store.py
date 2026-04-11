"""
Triple store for entity relationships.

File-based SQLite store for (subject, predicate, object) triples
extracted from document chunks. Persists across server restarts.
"""

import os
import sqlite3
from typing import Dict, List, Optional, Tuple


class TripleStore:
    """
    File-based SQLite store for knowledge triples.

    Each (user_id, thread_id) pair gets a dedicated SQLite file.
    Triples are extracted at index time and queried at retrieval time.
    """

    @classmethod
    def _get_db_path(cls, user_id: str, thread_id: str) -> str:
        """Get the file path for the triple store database."""
        db_dir = os.path.join("data", user_id, "triples")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, f"{thread_id}.db")

    @classmethod
    def _get_connection(cls, user_id: str, thread_id: str) -> sqlite3.Connection:
        """Get a connection to the triple store, creating the table if needed."""
        db_path = cls._get_db_path(user_id, thread_id)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                page_no INTEGER DEFAULT 0,
                UNIQUE(document_id, subject, predicate, object)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_subject ON triples (subject COLLATE NOCASE)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_object ON triples (object COLLATE NOCASE)"
        )
        conn.commit()
        return conn

    @classmethod
    def store_triples(
        cls,
        user_id: str,
        thread_id: str,
        document_id: str,
        triples: List[Dict[str, str]],
    ) -> int:
        """
        Store extracted triples for a document.

        Args:
            user_id: User ID
            thread_id: Thread ID
            document_id: Document these triples belong to
            triples: List of dicts with keys: subject, predicate, object, page_no

        Returns:
            Number of triples stored (new, not duplicates)
        """
        if not triples:
            return 0

        conn = cls._get_connection(user_id, thread_id)
        stored = 0
        try:
            for t in triples:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO triples (document_id, subject, predicate, object, page_no) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            document_id,
                            t["subject"],
                            t["predicate"],
                            t["object"],
                            t.get("page_no", 0),
                        ),
                    )
                    stored += 1
                except sqlite3.IntegrityError:
                    pass  # Duplicate triple, skip
            conn.commit()
        finally:
            conn.close()

        return stored

    @classmethod
    def query_by_entities(
        cls,
        user_id: str,
        thread_id: str,
        entities: List[str],
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """
        Find triples involving any of the given entities (as subject or object).

        Args:
            user_id: User ID
            thread_id: Thread ID
            entities: List of entity names to search for
            limit: Max triples to return

        Returns:
            List of triple dicts with keys: subject, predicate, object, document_id
        """
        db_path = cls._get_db_path(user_id, thread_id)
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        results = []
        try:
            for entity in entities:
                # Case-insensitive search using LIKE for partial matching
                cursor = conn.execute(
                    "SELECT DISTINCT subject, predicate, object, document_id "
                    "FROM triples "
                    "WHERE subject LIKE ? OR object LIKE ? "
                    "LIMIT ?",
                    (f"%{entity}%", f"%{entity}%", limit),
                )
                for row in cursor.fetchall():
                    results.append(
                        {
                            "subject": row[0],
                            "predicate": row[1],
                            "object": row[2],
                            "document_id": row[3],
                        }
                    )
        finally:
            conn.close()

        # Deduplicate
        seen = set()
        unique = []
        for t in results:
            key = (t["subject"].lower(), t["predicate"].lower(), t["object"].lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)

        return unique[:limit]

    @classmethod
    def get_context_for_query(
        cls, user_id: str, thread_id: str, query_entities: List[str]
    ) -> Optional[str]:
        """
        Get formatted triple context for injection into the retrieval/prompt.

        Returns a human-readable string of entity relationships, or None if
        no relevant triples found.
        """
        if not query_entities:
            return None

        triples = cls.query_by_entities(user_id, thread_id, query_entities)
        if not triples:
            return None

        lines = []
        for t in triples:
            lines.append(f"- {t['subject']} {t['predicate']} {t['object']}")

        return "Entity Relationships:\n" + "\n".join(lines)

    @classmethod
    def delete_document_triples(
        cls, user_id: str, thread_id: str, document_id: str
    ) -> int:
        """Delete all triples for a specific document. Returns count deleted."""
        db_path = cls._get_db_path(user_id, thread_id)
        if not os.path.exists(db_path):
            return 0

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM triples WHERE document_id = ?", (document_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    @classmethod
    def has_triples(cls, user_id: str, thread_id: str) -> bool:
        """Check if there are any triples stored for this user/thread."""
        db_path = cls._get_db_path(user_id, thread_id)
        if not os.path.exists(db_path):
            return False

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM triples")
            count = cursor.fetchone()[0]
            return count > 0
        except Exception:
            return False
        finally:
            conn.close()
