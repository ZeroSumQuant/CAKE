#!/usr/bin/env python3
"""watchdog.py - Stream Monitor for CAKE

Monitors stdout/stderr streams and triggers callbacks on error patterns.
Part of the CAKE (Claude Autonomy Kit Engine) system.
"""

import asyncio
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import IO, Callable, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass
class ErrorEvent:
    """Represents a detected error event."""

    error_type: str
    file_path: Optional[str]
    line_number: Optional[int]
    raw_output: str
    timestamp: datetime
    stream_source: str  # "stdout" or "stderr"


class Watchdog:
    """
    Stream monitor that detects error patterns and triggers interventions.

    Monitors stdout/stderr for error patterns and calls registered callbacks
    when patterns are detected. Non-blocking and thread-safe.
    """

    # Default error patterns to monitor
    DEFAULT_PATTERNS = {
        r"ImportError: No module named '(\w+)'": "ImportError",
        r"ModuleNotFoundError: No module named '(\w+)'": "ModuleNotFoundError",
        r"SyntaxError: .* \((.+), line (\d+)\)": "SyntaxError",
        r"AttributeError: .* has no attribute '(\w+)'": "AttributeError",
        r"TypeError: .* got an unexpected keyword argument '(\w+)'": "TypeError",
        r"NameError: name '(\w+)' is not defined": "NameError",
        r"FAILED tests/.*::(\w+)": "TestFailure",
        r"Coverage: (\d+)%": "CoverageDrop",
        r"AssertionError: (.*)": "AssertionError",
        r"FileNotFoundError: \[Errno 2\] No such file or directory: '(.+)'": "FileNotFoundError",
        r"PermissionError: \[Errno 13\] Permission denied: '(.+)'": "PermissionError",
        r"ConnectionError: (.*)": "ConnectionError",
        r"ValueError: (.*)": "ValueError",
        r"KeyError: '(\w+)'": "KeyError",
        r"IndexError: (.*)": "IndexError",
    }

    def __init__(self):
        """Initialize watchdog with default patterns."""
        self.patterns: Dict[Pattern, str] = {}
        self.callbacks: List[Callable[[ErrorEvent], None]] = []
        self._monitoring = False
        self._threads: List[threading.Thread] = []

        # Compile default patterns
        for pattern_str, error_type in self.DEFAULT_PATTERNS.items():
            self.add_pattern(pattern_str, error_type)

        logger.info("Watchdog initialized with %d patterns", len(self.patterns))

    def add_pattern(self, pattern: str, error_type: str) -> None:
        """
        Add new error pattern to monitor.

        Args:
            pattern: Regex pattern to match
            error_type: Classification for this pattern
        """
        try:
            compiled_pattern = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            self.patterns[compiled_pattern] = error_type
            logger.debug("Added pattern for %s: %s", error_type, pattern)
        except re.error as e:
            logger.error("Invalid regex pattern '%s': %s", pattern, e)

    def add_callback(self, callback: Callable[[ErrorEvent], None]) -> None:
        """
        Register callback to be called when errors are detected.

        Args:
            callback: Function to call with ErrorEvent
        """
        self.callbacks.append(callback)
        logger.debug("Registered callback: %s", callback.__name__)

    def monitor_stream(
        self, stream: IO, callback: Callable[[ErrorEvent], None]
    ) -> None:
        """
        Monitor stream and trigger callback on patterns.

        Args:
            stream: stdout or stderr stream object
            callback: Function to call with ErrorEvent

        Note: This method is non-blocking and runs in a separate thread.
        """
        stream_name = getattr(stream, "name", "unknown")

        def _monitor():
            logger.info("Starting monitoring of stream: %s", stream_name)
            try:
                for line in stream:
                    if not self._monitoring:
                        break

                    # Check line against all patterns
                    for pattern, error_type in self.patterns.items():
                        match = pattern.search(line)
                        if match:
                            # Extract file path and line number if available
                            file_path = None
                            line_number = None

                            # Try to extract file info from match groups
                            groups = match.groups()
                            if len(groups) >= 2 and error_type == "SyntaxError":
                                file_path = groups[0]
                                try:
                                    line_number = int(groups[1])
                                except (ValueError, IndexError):
                                    pass

                            # Create error event
                            event = ErrorEvent(
                                error_type=error_type,
                                file_path=file_path,
                                line_number=line_number,
                                raw_output=line.strip(),
                                timestamp=datetime.now(),
                                stream_source=stream_name,
                            )

                            # Call the specific callback
                            try:
                                callback(event)
                            except Exception as e:
                                logger.error("Callback error: %s", e)

                            # Call all registered callbacks
                            for cb in self.callbacks:
                                try:
                                    cb(event)
                                except Exception as e:
                                    logger.error("Registered callback error: %s", e)

                            # Log the detection
                            logger.info(
                                "Detected %s: %s", error_type, line.strip()[:100]
                            )

                            # Check for coverage drop
                            if error_type == "CoverageDrop":
                                coverage = int(match.group(1))
                                if coverage < 90:
                                    logger.warning(
                                        "Coverage dropped to %d%% (below 90%% threshold)",
                                        coverage,
                                    )

            except Exception as e:
                logger.error("Stream monitoring error on %s: %s", stream_name, e)
            finally:
                logger.info("Stopped monitoring stream: %s", stream_name)

        # Start monitoring in separate thread
        thread = threading.Thread(target=_monitor, daemon=True)
        thread.start()
        self._threads.append(thread)
        self._monitoring = True

    def start_monitoring(
        self,
        stdout: Optional[IO] = None,
        stderr: Optional[IO] = None,
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Start monitoring specified streams.

        Args:
            stdout: stdout stream to monitor
            stderr: stderr stream to monitor
            callback: Callback for all events
        """
        self._monitoring = True

        if callback:
            self.add_callback(callback)

        # Default callback that logs events
        def default_callback(event: ErrorEvent):
            logger.info(
                "Error detected: %s in %s", event.error_type, event.stream_source
            )

        if stdout:
            self.monitor_stream(stdout, callback or default_callback)

        if stderr:
            self.monitor_stream(stderr, callback or default_callback)

    def stop_monitoring(self) -> None:
        """Stop all monitoring threads."""
        self._monitoring = False

        # Wait for threads to finish
        for thread in self._threads:
            thread.join(timeout=1.0)

        self._threads.clear()
        logger.info("Watchdog monitoring stopped")

    def get_pattern_stats(self) -> Dict[str, int]:
        """Get statistics on pattern usage."""
        return {
            "total_patterns": len(self.patterns),
            "pattern_types": len(set(self.patterns.values())),
            "callbacks_registered": len(self.callbacks),
        }

    async def async_monitor_stream(
        self, stream: asyncio.StreamReader, stream_name: str = "unknown"
    ) -> None:
        """
        Async version of stream monitoring for asyncio compatibility.

        Args:
            stream: AsyncIO stream reader
            stream_name: Name of stream for logging
        """
        logger.info("Starting async monitoring of stream: %s", stream_name)

        try:
            async for line_bytes in stream:
                if not self._monitoring:
                    break

                line = line_bytes.decode("utf-8", errors="replace").strip()

                # Check patterns
                for pattern, error_type in self.patterns.items():
                    match = pattern.search(line)
                    if match:
                        event = ErrorEvent(
                            error_type=error_type,
                            file_path=None,
                            line_number=None,
                            raw_output=line,
                            timestamp=datetime.now(),
                            stream_source=stream_name,
                        )

                        # Call callbacks
                        for callback in self.callbacks:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event)
                            else:
                                callback(event)

                        logger.info("Async detected %s: %s", error_type, line[:100])

        except Exception as e:
            logger.error("Async stream monitoring error: %s", e)


# Example usage and testing
if __name__ == "__main__":
    import sys
    import time

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create watchdog
    watchdog = Watchdog()

    # Add custom pattern
    watchdog.add_pattern(r"CUSTOM_ERROR: (.+)", "CustomError")

    # Define callback
    def error_callback(event: ErrorEvent):
        print(f"\n🚨 ERROR DETECTED: {event.error_type}")
        print(f"   Source: {event.stream_source}")
        print(f"   Output: {event.raw_output}")
        if event.file_path:
            print(f"   File: {event.file_path}:{event.line_number}")

    # Register callback
    watchdog.add_callback(error_callback)

    print("Watchdog is monitoring... (Type error patterns to test)")
    print("Examples:")
    print("  ImportError: No module named 'requests'")
    print("  SyntaxError: invalid syntax (test.py, line 42)")
    print("  FAILED tests/test_example.py::test_function")
    print("  Coverage: 85%")
    print("\nPress Ctrl+C to stop\n")

    # Monitor stdin for testing
    try:
        watchdog.monitor_stream(sys.stdin, error_callback)

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping watchdog...")
        watchdog.stop_monitoring()
        print("Done!")
