import importlib
import logging
import platform
import sys
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest

from tests.plugins.json_report import (
    AnalyticsEntry,
    EnvEntry,
    JsonReportHandler,
    LogEntry,
    TestEntry,
    TestOutcome,
)


class JsonReportingPlugin:
    """
    State-managed Pytest plugin for real-time tagged JSON reporting.
    """

    def __init__(self, report_path: str):
        self.handler = JsonReportHandler(report_path)
        self.session_results: list[TestEntry] = []
        self._log_capture = InternalLogCapture()

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Capture environment at session start."""
        pkgs: dict[str, str] = {
            str(d.metadata["Name"]): str(d.version)
            for d in importlib.metadata.distributions()
        }

        plugs: dict[str, str] = {
            str(name): str(dist.version)
            for name, dist in session.config.pluginmanager.list_plugin_distinfo()
        }

        env = EnvEntry(
            python=sys.version,
            platform=platform.platform(),
            packages=pkgs,
            plugins=plugs,
        )
        self.handler.initialize(env, tag="environment")

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        """Capturing ALL logs for the test item."""
        logging.root.addHandler(self._log_capture)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[Any]
    ) -> Generator[None, Any, None]:
        """Real-time result streaming."""
        outcome = yield
        report = outcome.get_result()

        if report.when == "call":
            module_name = "unknown"
            if isinstance(item, pytest.Function):
                module_name = item.module.__name__
            elif hasattr(item, "nodeid"):
                module_name = item.nodeid.split("::")[0]

            captured_logs = [
                LogEntry(
                    name=item.nodeid,
                    msg=log["msg"],
                    levelname=log["levelname"],
                    created=log["created"],
                    filename=item.path.name if hasattr(item, "path") else "unknown",
                    module=module_name,
                )
                for log in self._log_capture.records
            ]

            test_entry = TestEntry(
                testname=report.nodeid,
                created=datetime.now(timezone.utc),
                duration=round(report.duration, 4),
                outcome=TestOutcome(report.outcome),
                error_message=str(report.longrepr) if report.failed else "",
                logs=captured_logs,
            )
            self.session_results.append(test_entry)
            self.handler.stream_item(test_entry)
            self._log_capture.records.clear()

    @pytest.hookimpl(trylast=True)
    def pytest_runtest_teardown(self, item: pytest.Item) -> None:
        """Remove log handler after teardown logs are captured."""
        logging.root.removeHandler(self._log_capture)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Analytics and closure."""
        if not self.session_results:
            return

        total = len(self.session_results)
        total_durration = sum(r.duration for r in self.session_results)

        stats = AnalyticsEntry(
            total=total,
            passed=sum(
                1 for r in self.session_results if r.outcome == TestOutcome.PASSED
            ),
            failed=sum(
                1 for r in self.session_results if r.outcome == TestOutcome.FAILED
            ),
            skipped=sum(
                1 for r in self.session_results if r.outcome == TestOutcome.SKIPPED
            ),
            test_duration=round(total_durration, 4),
        )
        self.handler.finalize(stats, tag="analytics")


class InternalLogCapture(logging.Handler):
    """Thread-safe log interceptor for pytest items."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(
            {
                "msg": record.getMessage(),
                "levelname": record.levelname,
                "created": datetime.fromtimestamp(record.created, tz=timezone.utc),
            }
        )
