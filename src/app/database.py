import json
import logging
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import IO, Any
from uuid import uuid4

import portalocker
from pydantic import TypeAdapter, ValidationError

from app.settings import settings

from .models import Task, TaskCreate, TaskPriority, TaskUpdate

task_validator = TypeAdapter(Task)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def get_task_by_id(task_id: uuid.UUID) -> Task | None:
    """
    Get a task by its ID.

    Args:
        task_id: The unique identifier of the task.

    Returns:
        Task dictionary if found, None otherwise.
    """
    raw_tasks = _get_all_tasks()
    for task in raw_tasks:
        if task.id == task_id:
            return task
    return None


def get_filtered_tasks(
    completed: bool | None = None,
    priority: TaskPriority | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[Task]:
    """
    Get all tasks with optional pagination.

    Args:
        completed: Filter by task completion status.
        priority: Filter by task priority.
        category: Filter by task category.
        search: Filter by search term.
        limit: Maximum number of tasks to return.

    Returns:
        List of task dictionaries.
    """
    tasks = _get_all_tasks()

    if not completed:
        tasks = [t for t in tasks if not t.is_completed]
    elif completed:
        tasks = [t for t in tasks if t.is_completed]

    if priority:
        tasks = [t for t in tasks if t.priority == priority]

    if category:
        tasks = [t for t in tasks if t.category == category]

    if search:
        search_lower = search.lower()
        tasks = [
            t
            for t in tasks
            if search_lower in t.title.lower() or search_lower in t.description.lower()
        ]

    return tasks[:limit]


def create(task_in: TaskCreate) -> Task:
    """
    Create a new task.

    Args:
        task_in: TaskCreate model with task details.

    Returns:
        The created task dictionary.

    Raises:
        DatabaseError: If database operations fail.
    """
    raw_tasks = _load_json()
    new_task = Task(
        id=uuid4(),
        creation_date=datetime.now(timezone.utc),
        is_completed=False,
        **task_in.model_dump(),
    )
    raw_tasks.append(new_task.model_dump(mode="json"))
    _save_to_json(raw_tasks)
    logger.info(f"Created task with ID: {new_task.id}")
    return new_task


def update(task_id: uuid.UUID, update_data: TaskUpdate) -> Task | None:
    """
    Update an existing task.

    Args:
        task_id: The unique identifier of the task to update.
        update_data: TaskUpdate model with fields to update.

    Returns:
        Updated task dictionary if found, None otherwise.

    Raises:
        DatabaseError: If database operations fail.
    """
    raw_tasks = _get_all_tasks()

    for index, task in enumerate(raw_tasks):
        if task.id == task_id:
            # Check for status transition
            data = update_data.model_dump(exclude_unset=True)
            new_status = data.get("is_completed")

            updated_task = task.model_copy(update=data)

            # Logic: Only set date if it just became completed
            if new_status is True and not task.is_completed:
                updated_task.completion_date = datetime.now(timezone.utc)
            elif new_status is False:
                updated_task.completion_date = None
            raw_tasks[index] = updated_task
            _save_task_list_to_json(raw_tasks)
            logger.info(f"Updated task with ID: {task_id}")
            return updated_task
    return None


def delete(task_id: uuid.UUID) -> bool:
    """
    Delete a task by its ID.

    Args:
        task_id: The unique identifier of the task to delete.

    Returns:
        True if task was deleted, False if not found.

    Raises:
        DatabaseError: If database operations fail.
    """
    raw_tasks = _get_all_tasks()
    initial_count = len(raw_tasks)
    remaining_tasks = [task for task in raw_tasks if task.id != task_id]

    if len(remaining_tasks) == initial_count:
        logger.warning(f"Attempted to delete non-existent task: {task_id}")
        return False

    _save_task_list_to_json(remaining_tasks)
    logger.info(f"Deleted task with ID: {task_id}")
    return True


@contextmanager
def _file_lock(file_handle: IO[Any]) -> Iterator[None]:
    """Context manager for file locking to prevent race conditions."""
    try:
        portalocker.lock(file_handle, portalocker.LOCK_EX)
        yield
    finally:
        portalocker.unlock(file_handle)


def _serialize_datetime(obj: Any) -> str:
    """Convert datetime objects to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _deserialize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Convert ISO format strings back to datetime objects."""
    for key, value in task.items():
        if isinstance(value, str):
            try:
                task[key] = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                pass
    return task


def _load_json() -> list[dict[str, Any]]:
    """
    Internal helper to read the file with proper error handling.

    Returns:
        List of tasks with datetime objects properly parsed.

    Raises:
        DatabaseError: If file operations fail critically.
    """
    if not os.path.exists(settings.db_file):
        logger.info(
            f"Database file {settings.db_file} does not exist, returning empty list"
        )
        return []
    try:
        with open(settings.db_file) as f:
            with _file_lock(f):
                content = f.read()
                if not content:
                    return []

                data = json.loads(content, object_hook=_deserialize_task)
                tasks = [_deserialize_task(task) for task in data]
                logger.debug(f"Loaded {len(tasks)} tasks from database")
                return tasks

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {settings.db_file}: {e}")
        backup_file = f"{settings.db_file}.backup"
        try:
            os.rename(settings.db_file, backup_file)
            logger.info(f"Corrupted file backed up to {backup_file}")
        except OSError:
            pass
        return []

    except PermissionError as e:
        logger.error(f"Permission denied accessing {settings.db_file}: {e}")
        raise DatabaseError("Permission denied accessing database file") from e

    except OSError as e:
        logger.error(f"OS error accessing {settings.db_file}: {e}")
        raise DatabaseError("Error accessing database file") from e


def _save_to_json(tasks: list[dict[str, Any]]) -> None:
    """
    Internal helper to write to the file with proper error handling.

    Args:
        tasks: List of tasks to save.

    Raises:
        DatabaseError: If file operations fail.
    """
    temp_file = f"{settings.db_file}.tmp"
    try:
        with open(temp_file, "w") as f:
            with _file_lock(f):
                # indent=4 makes the JSON file human-readable
                # default=str handles datetime serialization safely
                json.dump(
                    tasks,
                    f,
                    indent=4,
                    default=_serialize_datetime,
                )
                f.flush()
                os.fsync(f.fileno())
        os.replace(temp_file, settings.db_file)
        logger.debug(f"Saved {len(tasks)} tasks to database")

    except PermissionError as e:
        logger.error(f"Permission denied writing to {settings.db_file}: {e}")
        raise DatabaseError("Permission denied writing to database file") from e

    except OSError as e:
        logger.error(f"OS error writing to {settings.db_file}: {e}")
        raise DatabaseError("Error writing to database file") from e

    except Exception as e:
        logger.error(f"Failed to save json file: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise DatabaseError("Safe save failed unexpectedly") from e


def _save_task_list_to_json(tasks: list[Task]) -> None:
    """
    Helper to serialize a list of Task objects and save them to the file.

    Args:
        tasks: A list of Pydantic Task models.
    """
    serialized_data = [task.model_dump(mode="json") for task in tasks]

    _save_to_json(serialized_data)


def _get_all_tasks() -> list[Task]:
    """
    Get all tasks from database

    Returns:
        All tasks from database
    """
    raw_tasks = _load_json()
    return [
        task
        for task_dict in raw_tasks
        if (task := _validate_or_skip(task_dict)) is not None
    ]


def _validate_or_skip(data: dict[str, Any]) -> Task | None:
    try:
        # This is the "Automated Function" you are looking for
        return task_validator.validate_python(data)
    except ValidationError as e:
        logger.error(f"Skipping corrupt data: {e}")
        return None
