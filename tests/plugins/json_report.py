import json
from datetime import datetime
from enum import Enum

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_INDENT = 4
DEFAULT_TAG = ""


class TestOutcome(str, Enum):
    """Enumeration of possible test results for strict type safety."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportBase(BaseModel):
    """Base Pydantic model with shared configuration."""

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="ignore",
    )


class EnvEntry(ReportBase):
    """Environment metadata including system and package versions."""

    python: str
    platform: str
    packages: dict[str, str]
    plugins: dict[str, str]


class LogEntry(ReportBase):
    """Standardized log entry format captured during test execution."""

    name: str
    msg: str
    levelname: str
    created: datetime
    filename: str
    module: str


class TestEntry(ReportBase):
    """Core test result data captured after each test completion."""

    testname: str
    created: datetime
    duration: float = Field(..., description="Duration in seconds")
    outcome: TestOutcome
    error_message: str | None = Field(default="", validate_default=True)
    logs: list[LogEntry] = Field(default_factory=list)


class AnalyticsEntry(ReportBase):
    """Final session analytics generated at the end of the test run."""

    total: int
    passed: int
    failed: int
    skipped: int
    test_duration: float = Field(..., description="Duration in seconds")


class JsonReportHandler:
    """Handles the atomic, real-time streaming of JSON data to a file."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.lock = FileLock(f"{filepath}.lock")

    def initialize(self, entry: ReportBase, tag: str = DEFAULT_TAG) -> None:
        """Starts the session and writes the tagged environment block."""
        with self.lock:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write("[\n")
                data = entry.model_dump()
                if tag != DEFAULT_TAG:
                    data = {tag: data}
                f.write(json.dumps(data, indent=DEFAULT_INDENT, default=str))
                f.flush()

    def stream_item(self, entry: ReportBase, tag: str = DEFAULT_TAG) -> None:
        """Appends a tagged entry to the real-time stream."""
        with self.lock:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(",\n")
                data = entry.model_dump()
                if tag != DEFAULT_TAG:
                    data = {tag: data}
                f.write(json.dumps(data, indent=DEFAULT_INDENT, default=str))
                f.flush()

    def finalize(self, entry: ReportBase, tag: str = DEFAULT_TAG) -> None:
        """Writes the final tagged summary and closes the JSON array."""
        with self.lock:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(",\n")
                data = entry.model_dump()
                if tag != DEFAULT_TAG:
                    data = {tag: data}
                f.write(json.dumps(data, indent=DEFAULT_INDENT, default=str))
                f.write("\n]")
                f.flush()
