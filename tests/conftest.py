import pathlib
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Task, TaskCategory, TaskPriority
from app.settings import settings
from tests.plugins.reporter import JsonReportingPlugin

JSON_OUTPUT_FLAG = "--json-report"
DEFAULT_FILE = "test_results.json"
TEST_DB_FILE = "test_tasks.json"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Adds the command line flag to specify the output file."""
    parser.addoption(
        JSON_OUTPUT_FLAG,
        action="store",
        default=DEFAULT_FILE,
        help="Path to the JSON report file path where test results will be saved",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Registers the plugin instance with the config."""
    report_path = config.getoption(JSON_OUTPUT_FLAG)
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(JsonReportingPlugin(report_path))


@pytest.fixture(autouse=True)
def test_db(tmp_path: pathlib.Path) -> Iterator[pathlib.Path]:
    """Create a temporary database file for testing."""

    db_path = tmp_path / TEST_DB_FILE
    db_path.write_text("[]")

    settings.db_file = str(db_path)

    yield db_path


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_task_data() -> Task:
    """Reusable task data."""
    from datetime import datetime, timedelta

    due_date = datetime.now() + timedelta(days=1)
    creation_date = datetime.now() + timedelta(days=-1)

    sample = Task(
        id=uuid.uuid4(),
        title="Test Task",
        description="This is a test",
        creation_date=creation_date,
        is_completed=False,
        due_date=due_date,
        completion_date=None,
        category=TaskCategory.PERFORMANCE,
        priority=TaskPriority.HIGH,
    )
    return sample
