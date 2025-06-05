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
import re  # FIX: Added missing import
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
            # FIX: Enable WAL mode for better concurrency
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

            # Indexes for efficient querying
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

            # Pattern violations table
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

            # Command history table (for tracking attempted fixes)
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

            conn.commit()

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
        """  # Generate error signature (normalized for matching)
        signature = self._generate_error_signature(error_type, error_message)

        # Generate unique ID
        error_id = self._generate_id(
            f"{error_type}:{file_path}:{signature}:{datetime.now().isoformat()}"
        )

        # Calculate expiry
        expiry = datetime.now() + timedelta(hours=self.ttl_hours)

        # Create record
        record = ErrorRecord(
            error_id=error_id,
            error_type=error_type,
            error_signature=signature,
            file_path=file_path,
            line_number=line_number,
            error_message=error_message,
            attempted_fix=attempted_fix,
            context=context or {},
            timestamp=datetime.now(),
            expiry=expiry,
        )

        # Store in database
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO error_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.error_id,
                    record.error_type,
                    record.error_signature,
                    record.file_path,
                    record.line_number,
                    record.error_message,
                    record.attempted_fix,
                    json.dumps(record.context),
                    record.timestamp.isoformat(),
                    record.expiry.isoformat(),
                ),
            )
            conn.commit()

        logger.info("Recorded error: %s in %s", error_type, file_path)
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
            # Build query
            query = """SELECT * FROM error_records
                WHERE error_type = ?
                AND expiry > ?
            """
            params = [error_type, datetime.now().isoformat()]

            if file_path:
                query += " AND file_path = ?"
                params.append(file_path)

            if time_window_hours:
                cutoff = datetime.now() - timedelta(hours=time_window_hours)
                query += " AND timestamp > ?"
                params.append(cutoff.isoformat())

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)

            results = []
            for row in cursor:
                record_data = dict(row)
                record_data["context"] = json.loads(record_data["context"])
                record_data["timestamp"] = datetime.fromisoformat(
                    record_data["timestamp"]
                )
                results.append(record_data)

            return results

    def has_seen_error(
        self,
        error_type: str,
        error_message: str,
        file_path: Optional[str] = None,
        threshold_hours: int = 24,
    ) -> bool:
        """Check if we've seen this error recently.

        Args:
            error_type: Type of error
            error_message: Error message
            file_path: Optional file path
            threshold_hours: How far back to look

        Returns:
            True if error was seen within threshold
        """
        signature = self._generate_error_signature(error_type, error_message)

        with self._get_connection() as conn:
            query = """SELECT COUNT(*) FROM error_records
                WHERE error_signature = ?
                AND timestamp > ?
                AND expiry > ?
            """

            cutoff = datetime.now() - timedelta(hours=threshold_hours)
            params = [signature, cutoff.isoformat(), datetime.now().isoformat()]

            if file_path:
                query += " AND file_path = ?"
                params.append(file_path)

            cursor = conn.execute(query, params)
            count = cursor.fetchone()[0]

            return count > 0

    def record_pattern_violation(
        self, pattern_name: str, project: str, file_path: str, details: Dict[str, Any]
    ) -> str:
        """Record a pattern violation (anti-pattern usage).

        Args:
            pattern_name: Name of the pattern violated
            project: Project where it occurred
            file_path: File containing the violation
            details: Details about the violation

        Returns:
            Pattern ID for reference
        """
        pattern_id = self._generate_id(
            f"{pattern_name}:{project}:{file_path}:{datetime.now().isoformat()}"
        )

        expiry = datetime.now() + timedelta(hours=self.ttl_hours)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """INSERT INTO pattern_violations VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_id,
                    pattern_name,
                    project,
                    file_path,
                    json.dumps(details),
                    datetime.now().isoformat(),
                    expiry.isoformat(),
                ),
            )
            conn.commit()

        logger.info("Recorded pattern violation: %s in %s", pattern_name, project)
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
                violation_data["timestamp"] = datetime.fromisoformat(
                    violation_data["timestamp"]
                )
                results.append(violation_data)

            return results

    def record_command(
        self,
        command: str,
        success: bool,
        error_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a command execution attempt.

        Args:
            command: Command that was executed
            success: Whether it succeeded
            error_id: Related error ID if applicable
            context: Additional context

        Returns:
            Command ID for reference
        """
        command_id = self._generate_id(f"{command}:{datetime.now().isoformat()}")

        expiry = datetime.now() + timedelta(hours=self.ttl_hours)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """INSERT INTO command_history VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command_id,
                    command,
                    json.dumps(context or {}),
                    success,
                    error_id,
                    datetime.now().isoformat(),
                    expiry.isoformat(),
                ),
            )
            conn.commit()

        return command_id

    def get_failed_fixes(self, error_type: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent failed fix attempts for an error type.

        Args:
            error_type: Type of error
            limit: Maximum results to return

        Returns:
            List of failed fix attempts
        """
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
        """Clean up expired records.

        Returns:
            Number of records cleaned
        """
        with self._lock, self._get_connection() as conn:
            now = datetime.now().isoformat()

            # Clean error records
            cursor = conn.execute("DELETE FROM error_records WHERE expiry < ?", (now,))
            error_count = cursor.rowcount

            # Clean pattern violations
            cursor = conn.execute(
                "DELETE FROM pattern_violations WHERE expiry < ?", (now,)
            )
            pattern_count = cursor.rowcount

            # Clean command history
            cursor = conn.execute(
                "DELETE FROM command_history WHERE expiry < ?", (now,)
            )
            command_count = cursor.rowcount

            conn.commit()

            total = error_count + pattern_count + command_count
            if total > 0:
                logger.info("Cleaned up %s expired records", total)

            return total

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            # Count active records
            error_count = conn.execute(
                "SELECT COUNT(*) FROM error_records WHERE expiry > ?",
                (datetime.now().isoformat(),),
            ).fetchone()[0]

            pattern_count = conn.execute(
                "SELECT COUNT(*) FROM pattern_violations WHERE expiry > ?",
                (datetime.now().isoformat(),),
            ).fetchone()[0]

            command_count = conn.execute(
                "SELECT COUNT(*) FROM command_history WHERE expiry > ?",
                (datetime.now().isoformat(),),
            ).fetchone()[0]

            # Get most common errors
            cursor = conn.execute(
                """
                SELECT error_type, COUNT(*) as count
                FROM error_records
                WHERE expiry > ?
                GROUP BY error_type
                ORDER BY count DESC
                LIMIT 5
            """,
                (datetime.now().isoformat(),),
            )

            common_errors = [
                {"error_type": row["error_type"], "count": row["count"]}
                for row in cursor
            ]

            # Get most violated patterns
            cursor = conn.execute(
                """SELECT pattern_name, COUNT(*) as count
                FROM pattern_violations
                WHERE expiry > ?
                GROUP BY pattern_name
                ORDER BY count DESC
                LIMIT 5
            """,
                (datetime.now().isoformat(),),
            )

            common_patterns = [
                {"pattern_name": row["pattern_name"], "count": row["count"]}
                for row in cursor
            ]

            return {
                "active_errors": error_count,
                "active_patterns": pattern_count,
                "active_commands": command_count,
                "common_errors": common_errors,
                "common_patterns": common_patterns,
                "ttl_hours": self.ttl_hours,
            }

    def _generate_error_signature(self, error_type: str, error_message: str) -> str:
        """Generate normalized signature for error matching.

        Removes specific values to create reusable patterns.
        """
        signature = f"{error_type}:"

        # Normalize the error message
        normalized = error_message.lower()

        # Remove specific file paths
        normalized = re.sub(r"[/\\][^\s]+", "<path>", normalized)

        # Remove line numbers
        normalized = re.sub(r"line \d+", "line <n>", normalized)

        # Remove quoted strings
        normalized = re.sub(r"'[^']*'", "'<value>'", normalized)
        normalized = re.sub(r'"[^"]*"', '"<value>"', normalized)

        # Remove memory addresses
        normalized = re.sub(r"0x[0-9a-fA-F]+", "<addr>", normalized)

        signature += normalized[:200]  # Limit length

        return signature

    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:16]


class RecallAnalyzer:
    """Analyzes patterns in recall database for insights."""

    def __init__(self, recall_db: RecallDB):
        """Initialize analyzer with recall database."""
        self.db = recall_db

    def get_repeat_offenders(self) -> List[Dict[str, Any]]:
        """Find errors that occur repeatedly."""
        with self.db._get_connection() as conn:
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
                results.append(
                    {
                        "error_type": row["error_type"],
                        "file_path": row["file_path"],
                        "repeat_count": row["repeat_count"],
                        "fixes_tried": (
                            row["fixes_tried"].split(" | ")
                            if row["fixes_tried"]
                            else []
                        ),
                    }
                )

            return results

    def get_intervention_suggestions(self) -> List[Dict[str, Any]]:
        """Generate intervention suggestions based on patterns."""
        suggestions = []

        # Check for repeated errors
        repeat_offenders = self.get_repeat_offenders()
        for offender in repeat_offenders:
            if offender["repeat_count"] >= 3:
                suggestions.append(
                    {
                        "type": "escalate",
                        "reason": (
                            f"{offender['error_type']} in {offender['file_path']} "
                            f"failed {offender['repeat_count']} times"
                        ),
                        "tried_fixes": offender["fixes_tried"],
                    }
                )

        # Check for pattern clusters
        stats = self.db.get_statistics()
        for pattern in stats["common_patterns"]:
            if pattern["count"] >= 3:
                suggestions.append(
                    {
                        "type": "training_needed",
                        "reason": (
                            f"Pattern '{pattern['pattern_name']}' violated "
                            f"{pattern['count']} times"
                        ),
                        "pattern": pattern["pattern_name"],
                    }
                )

        return suggestions


# Example usage for testing
if __name__ == "__main__":
    import tempfile

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "recall.db"
        recall_db = RecallDB(db_path, ttl_hours=24)

        # Record some errors
        error_id1 = recall_db.record_error(
            error_type="ModuleNotFoundError",
            error_message="ModuleNotFoundError: No module named 'requests'",
            file_path="main.py",
            line_number=42,
            attempted_fix="pip install request",  # Note the typo
            context={"stage": "execute", "task": "API development"},
        )

        # Record the same error again
        error_id2 = recall_db.record_error(
            error_type="ModuleNotFoundError",
            error_message="ModuleNotFoundError: No module named 'requests'",
            file_path="main.py",
            line_number=42,
            attempted_fix="pip install requests-library",  # Wrong package name
            context={"stage": "execute", "task": "API development"},
        )

        # Check if we've seen this error
        seen = recall_db.has_seen_error(
            "ModuleNotFoundError",
            "ModuleNotFoundError: No module named 'requests'",
            "main.py",
        )
        print(f"Have we seen this error before? {seen}")

        # Get similar errors
        similar = recall_db.get_similar_errors("ModuleNotFoundError", "main.py")
        print(f"\nFound {len(similar)} similar errors:")
        for error in similar:
            print(f"  - {error['timestamp']}: {error['attempted_fix']}")

        # Record a pattern violation
        recall_db.record_pattern_violation(
            pattern_name="copy_paste",
            project="CAKE",
            file_path="utils.py",
            details={
                "duplicate_lines": 50,
                "locations": ["line 100-150", "line 200-250"],
            },
        )

        # Get statistics
        print("\nRecallDB Statistics:")
        stats = recall_db.get_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Test analyzer
        analyzer = RecallAnalyzer(recall_db)

        print("\nRepeat Offenders:")
        for offender in analyzer.get_repeat_offenders():
            print(f"  - {offender}")

        print("\nIntervention Suggestions:")
        for suggestion in analyzer.get_intervention_suggestions():
            print(f"  - {suggestion['type']}: {suggestion['reason']}")
