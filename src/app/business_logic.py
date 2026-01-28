import csv
import logging
import uuid
from datetime import datetime, timezone

from app.database import (
    DatabaseError,
    _get_all_tasks,
    get_filtered_tasks,
    get_task_by_id,
)
from app.models import Task, TaskCategory, TaskPriority, TaskReport

logger = logging.getLogger(__name__)

DEFAULT_CSV_FILE = "task_export.csv"


def get_most_recent() -> Task | None:
    """
    Get the most recently created task using object attributes.
    """
    tasks = _get_all_tasks()
    if not tasks:
        return None
    most_recent = max(tasks, key=lambda x: x.creation_date)
    return most_recent


def get_task_age(task_id: uuid.UUID) -> str | None:
    """
    Calculate the age of a task.
    """
    task = get_task_by_id(task_id)
    if not task:
        return None
    now = datetime.now(timezone.utc)
    diff = now - task.creation_date
    return str(diff)


def generate_csv_file(
    filename: str = DEFAULT_CSV_FILE,
    completed: bool | None = None,
    category: TaskCategory | None = None,
) -> str | None:
    """
    Generate a CSV representation of filtered tasks.

    Args:
        filename: the filepath to save the CSV file.
        completed: Optional filter by completion status.
        category: Optional filter by category.

    Returns:
        A string containing the CSV data.
    """
    try:
        tasks = get_filtered_tasks(completed=completed, category=category)
        if not tasks:
            logger.info("No tasks found for CSV export")
            return None

        headers = list(Task.model_fields.keys())

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()

            for task in tasks:
                # Convert Pydantic object to dict
                task_dict = task.model_dump()

                row = {}
                for k, v in task_dict.items():
                    if k in headers:
                        if isinstance(v, (list, datetime, uuid.UUID)):
                            row[k] = str(v)
                        else:
                            row[k] = v

                writer.writerow(row)

        logger.info(f"Successfully saved {len(tasks)} tasks to {filename}")
        return filename

    except OSError as e:
        logger.error(f"File system error when writing CSV: {e}")
        raise DatabaseError(f"Could not write to file {filename}") from e

    except Exception as e:
        logger.error(f"Failed to generate CSV file: {e}")
        raise DatabaseError("Unexpected error generating CSV export") from e


def generate_report() -> TaskReport:
    """
    Calculate statistics and generate a TaskReport model using strict object types.

    Returns:
        TaskReport: A model containing task analytics.

    Raises:
        DatabaseError: If database operations fail.
    """
    try:
        tasks = _get_all_tasks()
        total = len(tasks)

        # calculate in for loop instead of oneliner
        completed_tasks: list[Task] = []

        cat_counts: dict[TaskCategory, int] = {}
        prio_counts: dict[TaskPriority, int] = {}

        for t in tasks:
            cat_name = t.category
            prio_name = t.priority
            cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1
            prio_counts[prio_name] = prio_counts.get(prio_name, 0) + 1
            if t.is_completed:
                completed_tasks.append(t)

        total_time: float = 0.0
        count_with_time: int = 0

        for t in completed_tasks:
            if t.completion_date and t.creation_date:
                duration = t.completion_date - t.creation_date
                total_time += duration.total_seconds()
                count_with_time += 1

        avg_time = (total_time / count_with_time) if count_with_time > 0 else 0.0

        logger.info("Generated task report successfully")

        return TaskReport(
            total_tasks=total,
            completed_tasks=len(completed_tasks),
            avg_completion_time_seconds=round(avg_time, 2),
            tasks_by_category=cat_counts,
            tasks_by_priority=prio_counts,
        )

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise DatabaseError("Error calculating report statistics") from e


def validate_task_completion(task: Task) -> bool:
    """Returns True if all dependencies are completed."""

    if not task.dependencies:
        return True

    for dep_id in task.dependencies:
        dep_task = get_task_by_id(dep_id)
        if not dep_task or not dep_task.is_completed:
            return False
    return True
