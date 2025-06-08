#!/usr/bin/env python3
"""recall_db.py - 24-hour error pattern memory for CAKE

Tracks Claude's repeated mistakes with automatic expiry to prevent
him from making the same error twice in the same day.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import hashlib
import json
import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""

    error_id: str
    error_type: str
    error_signature: str
    file_path: str
    line_number: Optional[int]
    error_message: str
    attempted_fix: Optional[str]
    context: Dict[str, Any]
    timestamp: datetime
    expiry: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["expiry"] = self.expiry.isoformat()
        return data

    @classmethod
    def from_dict(cls: type["ErrorRecord"], data: Dict[str, Any]) -> "ErrorRecord":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["expiry"] = datetime.fromisoformat(data["expiry"])
        return cls(**data)


@dataclass
class PatternViolation:
    """Record of a pattern violation."""

    pattern_id: str
    pattern_name: str
    project: str
    file_path: str
    details: Dict[str, Any]
    timestamp: datetime
    expiry: datetime


class RecallDB:
    """
    24-hour memory for tracking repeated errors and patterns.

    Prevents Claude from making the same mistakes repeatedly within a day.
    """

    def __init__(self, db_path: Path, ttl_hours: int = 24):
        """
        Initialize RecallDB.

        Args:
            db_path: Path to SQLite database
            ttl_hours: Time-to-live for records in hours (default: 24)
        """
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self._lock = threading.Lock()

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Clean up expired records on startup
        self.cleanup_expired()

        logger.info("RecallDB initialized at %s with %sh TTL", db_path, ttl_hours)

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # Error records table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS error_records (
                    error_id TEXT PRIMARY KEY,
                    error_type TEXT NOT NULL,
                    error_signature TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER,
                    error_message TEXT NOT NULL,
                    attempted_fix TEXT,
                    context TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    expiry TEXT NOT NULL
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_error_type_file
                ON error_records(error_type, file_path)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_expiry
                ON error_records(expiry)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signature
                ON error_records(error_signature)
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pattern_violations (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_name TEXT NOT NULL,
                    project TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    expiry TEXT NOT NULL
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pattern_name
                ON pattern_violations(pattern_name)
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_history (
                    command_id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    context TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_id TEXT,
                    timestamp TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    FOREIGN KEY (error_id) REFERENCES error_records(error_id)
                )
            """
            )
            conn.commit() # Commit table creation before trying to read schema

            # Log the schema for debugging
            try:
                cursor = conn.execute("PRAGMA table_info(error_records);")
                schema_info = cursor.fetchall()
                logger.debug(f"Schema for error_records after creation: {schema_info}")
                is_present = any(col[1] == 'error_message' for col in schema_info)
                logger.debug(f"Column 'error_message' present in schema after creation: {is_present}")
                if not is_present:
                    logger.error("CRITICAL SCHEMA ISSUE: 'error_message' column NOT FOUND in error_records after table creation attempt.")
            except Exception as e_pragma:
                logger.error(f"Failed to retrieve schema info for error_records: {e_pragma}", exc_info=True)

            # Log the schema for command_history table for debugging
            try:
                cursor = conn.execute("PRAGMA table_info(command_history);")
                schema_info_cmd = cursor.fetchall()
                logger.debug(f"Schema for command_history after creation: {schema_info_cmd}")
                is_error_id_present = any(col[1] == 'error_id' for col in schema_info_cmd)
                logger.debug(f"Column 'error_id' present in command_history schema after creation: {is_error_id_present}")
                if not is_error_id_present:
                    logger.error("CRITICAL SCHEMA ISSUE: 'error_id' column NOT FOUND in command_history after table creation attempt.")
            except Exception as e_pragma_cmd:
                logger.error(f"Failed to retrieve schema info for command_history: {e_pragma_cmd}", exc_info=True)

            conn.commit() # Ensure logging transaction is committed if any

    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def record_error(
        self,
        error_type: str,
        error_message: str,
        file_path: str,
        line_number: Optional[int] = None,
        attempted_fix: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record an error occurrence.

        Args:
            error_type: Type of error (e.g., 'ModuleNotFoundError')
            error_message: Full error message
            file_path: File where error occurred
            line_number: Line number if available
            attempted_fix: What fix was attempted
            context: Additional context

        Returns:
            Error ID for reference
        """
        signature = self._generate_error_signature(error_type, error_message)
        error_id = self._generate_id(
            f"{error_type}:{file_path}:{signature}:{datetime.now().isoformat()}"
        )
        expiry = datetime.now() + timedelta(hours=self.ttl_hours)
        record_timestamp = datetime.now() # Use a single timestamp for the record

        # Create record dataclass instance for clarity, though not strictly needed for this insert
        # record = ErrorRecord(...)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO error_records (
                    error_id, error_type, error_signature, file_path, line_number,
                    error_message, attempted_fix, context, timestamp, expiry
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    error_id,
                    error_type,
                    signature,
                    file_path,
                    line_number,
                    error_message, # This is the critical parameter
                    attempted_fix,
                    json.dumps(context or {}), # Ensure context is always a dict then dumped
                    record_timestamp.isoformat(),
                    expiry.isoformat(),
                ),
            )
            conn.commit()

        logger.info("Recorded error: %s in %s (ID: %s)", error_type, file_path, error_id)
        return error_id

    def get_similar_errors(
        self,
        error_type: str,
        file_path: Optional[str] = None,
        time_window_hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get similar errors from recent history.

        Args:
            error_type: Type of error to search for
            file_path: Optional file path to filter by
            time_window_hours: Optional time window (default: full TTL)

        Returns:
            List of similar error records
        """
        with self._get_connection() as conn:
            query = """SELECT * FROM error_records
                WHERE error_type = ?
                AND expiry > ?
            """
            params: List[Any] = [error_type, datetime.now().isoformat()]

            if file_path:
                query += " AND file_path = ?"
                params.append(file_path)

            if time_window_hours:
                cutoff = datetime.now() - timedelta(hours=time_window_hours)
                query += " AND timestamp > ?"
                params.append(cutoff.isoformat())

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, tuple(params)) # Ensure params is a tuple

            results = []
            for row in cursor:
                record_data = dict(row)
                record_data["context"] = json.loads(record_data["context"])
                record_data["timestamp"] = datetime.fromisoformat(
                    record_data["timestamp"]
                )
                record_data["expiry"] = datetime.fromisoformat( # Also convert expiry
                    record_data["expiry"]
                )
                results.append(record_data)

            return results

    def is_repeat_error(
        self,
        error_message: str, # Changed from error_type for more specific check
        file_path: Optional[str] = None, # error_message is more specific than error_type
        error_type: Optional[str] = None, # Keep error_type for signature generation consistency
        threshold_hours: int = 24,
    ) -> bool:
        """Check if we've seen this specific error recently based on signature.

        Args:
            error_message: The full error message.
            file_path: Optional file path where error occurred.
            error_type: The general type of the error (e.g., ModuleNotFoundError).
            threshold_hours: How far back to look.

        Returns:
            True if error signature was seen within threshold.
        """
        # Use a more specific error_type if provided, otherwise try to extract from message
        actual_error_type = error_type if error_type else self._extract_error_type_from_message(error_message)
        signature = self._generate_error_signature(actual_error_type, error_message)

        with self._get_connection() as conn:
            query = """SELECT COUNT(*) FROM error_records
                WHERE error_signature = ?
                AND timestamp > ?
                AND expiry > ?
            """
            cutoff = datetime.now() - timedelta(hours=threshold_hours)
            params: List[Any] = [signature, cutoff.isoformat(), datetime.now().isoformat()]

            if file_path:
                query += " AND file_path = ?"
                params.append(file_path)

            cursor = conn.execute(query, tuple(params))
            count = cursor.fetchone()[0]

            return count > 0

    def record_pattern_violation(
        self, pattern_name: str, project: str, file_path: str, details: Dict[str, Any]
    ) -> str:
        """Record a pattern violation (anti-pattern usage)."""
        pattern_id = self._generate_id(
            f"{pattern_name}:{project}:{file_path}:{datetime.now().isoformat()}"
        )
        expiry = datetime.now() + timedelta(hours=self.ttl_hours)
        timestamp = datetime.now().isoformat()

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """INSERT INTO pattern_violations (
                    pattern_id, pattern_name, project, file_path, details, timestamp, expiry
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern_id,
                    pattern_name,
                    project,
                    file_path,
                    json.dumps(details),
                    timestamp,
                    expiry.isoformat(),
                ),
            )
            conn.commit()
        logger.info("Recorded pattern violation: %s in %s (ID: %s)", pattern_name, project, pattern_id)
        return pattern_id

    def get_pattern_violations(self, pattern_name: str) -> List[Dict[str, Any]]:
        """Get recent violations of a specific pattern."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM pattern_violations
                WHERE pattern_name = ?
                AND expiry > ?
                ORDER BY timestamp DESC
            """,
                (pattern_name, datetime.now().isoformat()),
            )
            results = []
            for row in cursor:
                violation_data = dict(row)
                violation_data["details"] = json.loads(violation_data["details"])
                violation_data["timestamp"] = datetime.fromisoformat(violation_data["timestamp"])
                violation_data["expiry"] = datetime.fromisoformat(violation_data["expiry"])
                results.append(violation_data)
            return results

    def record_command(
        self,
        command: str,
        success: bool,
        error_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a command execution attempt."""
        command_id = self._generate_id(f"{command}:{datetime.now().isoformat()}")
        expiry = datetime.now() + timedelta(hours=self.ttl_hours)
        timestamp = datetime.now().isoformat()

        with self._lock, self._get_connection() as conn:
            # Check if error_id column exists
            cursor = conn.execute("PRAGMA table_info(command_history);")
            columns = [row[1] for row in cursor.fetchall()]
            error_id_column_exists = 'error_id' in columns

            if error_id_column_exists:
                conn.execute(
                    """INSERT INTO command_history (
                        command_id, command, context, success, error_id, timestamp, expiry
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        command_id,
                        command,
                        json.dumps(context or {}),
                        success,
                        error_id, # This will be used
                        timestamp,
                        expiry.isoformat(),
                    ),
                )
            else:
                logger.warning("Outdated 'command_history' schema: 'error_id' column missing. Recording command without error_id linkage.")
                conn.execute(
                    """INSERT INTO command_history (
                        command_id, command, context, success, timestamp, expiry
                       ) VALUES (?, ?, ?, ?, ?, ?)""", # error_id parameter and column omitted
                    (
                        command_id,
                        command,
                        json.dumps(context or {}),
                        success,
                        # error_id is omitted here
                        timestamp,
                        expiry.isoformat(),
                    ),
                )
            conn.commit()
        logger.info("Recorded command: %s (Success: %s, ID: %s)", command[:100], success, command_id)
        return command_id

    def get_failed_fixes(self, error_type: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent failed fix attempts for an error type."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT ch.command, ch.context, ch.timestamp, er.error_message
                FROM command_history ch
                JOIN error_records er ON ch.error_id = er.error_id
                WHERE er.error_type = ?
                AND ch.success = 0
                AND ch.expiry > ?
                ORDER BY ch.timestamp DESC
                LIMIT ?
            """,
                (error_type, datetime.now().isoformat(), limit),
            )
            results = []
            for row in cursor:
                fix_data = dict(row)
                fix_data["context"] = json.loads(fix_data["context"])
                fix_data["timestamp"] = datetime.fromisoformat(fix_data["timestamp"])
                results.append(fix_data)
            return results

    def cleanup_expired(self) -> int:
        """Clean up expired records."""
        with self._lock, self._get_connection() as conn:
            now = datetime.now().isoformat()
            counts = {"errors": 0, "patterns": 0, "commands": 0}

            cursor = conn.execute("DELETE FROM error_records WHERE expiry < ?", (now,))
            counts["errors"] = cursor.rowcount

            cursor = conn.execute("DELETE FROM pattern_violations WHERE expiry < ?", (now,))
            counts["patterns"] = cursor.rowcount

            cursor = conn.execute("DELETE FROM command_history WHERE expiry < ?", (now,))
            counts["commands"] = cursor.rowcount

            conn.commit()
            total_cleaned = sum(counts.values())
            if total_cleaned > 0:
                logger.info(f"Cleaned up {total_cleaned} expired records: {counts}")
            return total_cleaned

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            now_iso = datetime.now().isoformat()
            error_count = conn.execute("SELECT COUNT(*) FROM error_records WHERE expiry > ?", (now_iso,)).fetchone()[0]
            pattern_count = conn.execute("SELECT COUNT(*) FROM pattern_violations WHERE expiry > ?", (now_iso,)).fetchone()[0]
            command_count = conn.execute("SELECT COUNT(*) FROM command_history WHERE expiry > ?", (now_iso,)).fetchone()[0]

            common_errors_cursor = conn.execute(
                "SELECT error_type, COUNT(*) as count FROM error_records WHERE expiry > ? GROUP BY error_type ORDER BY count DESC LIMIT 5", (now_iso,)
            )
            common_errors = [{"error_type": row["error_type"], "count": row["count"]} for row in common_errors_cursor]

            common_patterns_cursor = conn.execute(
                "SELECT pattern_name, COUNT(*) as count FROM pattern_violations WHERE expiry > ? GROUP BY pattern_name ORDER BY count DESC LIMIT 5", (now_iso,)
            )
            common_patterns = [{"pattern_name": row["pattern_name"], "count": row["count"]} for row in common_patterns_cursor]

            return {
                "active_errors": error_count, "active_patterns": pattern_count, "active_commands": command_count,
                "common_errors": common_errors, "common_patterns": common_patterns, "ttl_hours": self.ttl_hours,
            }

    def _generate_error_signature(self, error_type: str, error_message: str) -> str:
        """Generate normalized signature for error matching."""
        signature_parts = [error_type.lower()]
        normalized_message = error_message.lower()
        normalized_message = re.sub(r"[/\\][^\s]+(\.\w+)?", "<path>", normalized_message) # More robust path removal
        normalized_message = re.sub(r"line \d+", "line <n>", normalized_message)
        normalized_message = re.sub(r"\'[^\']*\'", "'<val>'", normalized_message)
        normalized_message = re.sub(r'\"[^\"]*\"', '"<val>"', normalized_message)
        normalized_message = re.sub(r"0x[0-9a-fA-F]+", "<addr>", normalized_message)
        normalized_message = re.sub(r"\d+", "<num>", normalized_message) # Normalize all numbers

        # Keep only alphanumeric and basic punctuation for broader matching
        # This helps group similar errors even if specific values/symbols change
        normalized_message = re.sub(r"[^a-z0-9\s\<\>\_\-\:\.\,]", "", normalized_message)
        normalized_message = re.sub(r"\s+", " ", normalized_message).strip() # Consolidate whitespace

        signature_parts.append(normalized_message[:200])
        return ":".join(signature_parts)

    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.md5(content.encode('utf-8'), usedforsecurity=False).hexdigest()[:16]

    def _extract_error_type_from_message(self, error_message: str) -> str:
        """Basic extraction of error type from a message string if not provided."""
        match = re.match(r"(\w*Error|\w*Exception)", error_message)
        if match:
            return match.group(1)
        return "UnknownError"


class RecallAnalyzer:
    """Analyzes patterns in recall database for insights."""

    def __init__(self, recall_db: RecallDB):
        """Initialize analyzer with recall database."""
        self.db = recall_db

    def get_repeat_offenders(self) -> List[Dict[str, Any]]:
        """Find errors that occur repeatedly."""
        with self.db._get_connection() as conn: # Accessing protected member, but this is a closely related class
            cursor = conn.execute(
                """
                SELECT error_type, file_path, COUNT(*) as repeat_count,
                       GROUP_CONCAT(attempted_fix, ' | ') as fixes_tried
                FROM error_records
                WHERE expiry > ?
                GROUP BY error_type, file_path
                HAVING COUNT(*) > 1
                ORDER BY repeat_count DESC
            """,
                (datetime.now().isoformat(),),
            )
            results = []
            for row in cursor:
                results.append(dict(row)) # Convert row to dict
            return results

    def get_intervention_suggestions(self) -> List[Dict[str, Any]]:
        """Generate intervention suggestions based on patterns."""
        suggestions = []
        repeat_offenders = self.get_repeat_offenders()
        for offender in repeat_offenders:
            if offender["repeat_count"] >= 3:
                suggestions.append({
                    "type": "escalate_repeated_error",
                    "reason": f"{offender['error_type']} in {offender['file_path']} failed {offender['repeat_count']} times.",
                    "details": offender,
                })

        stats = self.db.get_statistics()
        for pattern in stats.get("common_patterns", []):
            if pattern["count"] >= 3:
                suggestions.append({
                    "type": "address_pattern_violation",
                    "reason": f"Pattern '{pattern['pattern_name']}' violated {pattern['count']} times.",
                    "details": pattern,
                })
        return suggestions


# Example usage for testing
if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "recall_test.db"
        logger.info(f"Using temporary RecallDB at: {db_path}")
        recall_db = RecallDB(db_path, ttl_hours=1) # Short TTL for testing cleanup

        err_type = "ModuleNotFoundError"
        err_msg = "ModuleNotFoundError: No module named 'non_existent_package'"
        file_p = "src/main.py"

        recall_db.record_error(err_type, err_msg, file_p, 10, "pip install non_existent_package", {"task": "task1"})
        recall_db.record_error(err_type, err_msg, file_p, 10, "pip install non_existent_package --force", {"task": "task2"})

        is_repeat = recall_db.is_repeat_error(error_message=err_msg, file_path=file_p, error_type=err_type)
        logger.info(f"Is '{err_msg}' a repeat error in '{file_p}'? {is_repeat}")

        similar = recall_db.get_similar_errors(error_type=err_type, file_path=file_p)
        logger.info(f"Similar errors found: {len(similar)}")
        for err in similar:
            logger.info(f"  - Attempted fix: {err.get('attempted_fix')}, Context: {err.get('context')}")

        recall_db.record_pattern_violation("GodClass", "ProjectCake", "cake_controller.py", {"lines": 1500})

        stats = recall_db.get_statistics()
        logger.info(f"RecallDB Stats: {json.dumps(stats, indent=2)}")

        analyzer = RecallAnalyzer(recall_db)
        suggestions = analyzer.get_intervention_suggestions()
        logger.info(f"Intervention Suggestions: {json.dumps(suggestions, indent=2)}")

        logger.info("Cleaning up expired records (should be none yet with 1h TTL unless test runs >1h)...")
        cleaned_count = recall_db.cleanup_expired()
        logger.info(f"Cleaned {cleaned_count} records.")

        logger.info("RecallDB test completed.")
