import os
import tempfile
import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from starlette.responses import FileResponse

from . import business_logic as bl
from . import database
from .business_logic import DEFAULT_CSV_FILE
from .models import Task, TaskCategory, TaskCreate, TaskPriority, TaskReport, TaskUpdate

router = APIRouter()


@router.get(
    "/tasks",
    summary="Get all tasks",
    description="Retrieve a list of all tasks with optional pagination",
    response_description="List of tasks",
)
def get_tasks(
    completed: bool | None = None,
    priority: TaskPriority | None = None,
    category: TaskCategory | None = None,
    search: str | None = None,
    limit: Annotated[
        int, Query(ge=1, le=1000, description="Maximum number of tasks to return")
    ] = 100,
) -> list[Task]:
    """
    Retrieve Filtered tasks by status, priority, category or search text

    - **completed**: Filter by task completion status.
    - **priority**: Filter by task priority.
    - **category**: Filter by task category.
    - **search**: Filter by search text.
    - **limit**: Maximum number of tasks to return (default: 100, max: 1000)
    """
    return database.get_filtered_tasks(completed, priority, category, search, limit)


@router.get(
    "/tasks/{task_id}",
    summary="Get a task by ID",
    description="Retrieve a specific task by its unique identifier",
    response_description="The requested task",
)
def get_task(task_id: uuid.UUID) -> Task:
    """
    Retrieve a specific task by ID.

    - **task_id**: The unique identifier of the task
    """
    task = database.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return task


@router.get(
    "/tasks/{task_id}/age",
    summary="Get the age of task",
    description="Get the age of task",
    response_description="The requested task",
)
def get_task_age(task_id: uuid.UUID) -> str:
    """
    Get the task age.

    """
    age = bl.get_task_age(task_id)
    if not age:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return age


@router.post(
    "/tasks",
    status_code=HTTPStatus.CREATED,
    summary="Create a new task",
    description="Create a new task with title, description, and due date",
    response_description="The created task",
)
def create_task(task_in: TaskCreate) -> Task:
    """
    Create a new task.

    - **title**: Task title (1-200 characters)
    - **description**: Task description (1-2000 characters)
    - **due_date**: Task due date (must be in the future)
    """
    return database.create(task_in)


@router.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Update an existing task's details or completion status",
    response_description="The updated task",
)
def update_task(task_id: uuid.UUID, task_update: TaskUpdate) -> Task:
    """
    Update an existing task.

    - **task_id**: The unique identifier of the task
    - **title**: New task title (optional)
    - **description**: New task description (optional)
    - **due_date**: New due date (optional, must be in the future)
    - **is_completed**: Completion status (optional)
    """
    current_task = database.get_task_by_id(task_id)
    if not current_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_update.is_completed is True:
        if not bl.validate_task_completion(current_task):
            raise HTTPException(
                status_code=400,
                detail="Cannot complete task: Unresolved dependencies exist.",
            )

    updated_task = database.update(task_id, task_update)
    if not updated_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated_task


@router.delete(
    "/tasks/{task_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a task",
    description="Delete a task by its unique identifier",
    response_description="No content",
)
def delete_task(task_id: uuid.UUID) -> None:
    """
    Delete a task.

    - **task_id**: The unique identifier of the task to delete
    """
    success = database.delete(task_id)
    if not success:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return


@router.get(
    "/tasks/recent",
    summary="Get recent tasks",
    description="Get recent tasks",
    response_description="The recent tasks",
)
def get_recent_task() -> Task:
    """
    Get the most recently created task.

    """
    task = bl.get_most_recent()
    if not task:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No Task available (DB is empty)"
        )
    return task


@router.get(
    "/tasks/export/csv",
    summary="Export tasks to CSV",
    description="Export tasks to CSV format and download the file",
    response_description="The generated CSV file",
)
def export_tasks_csv(
    background_tasks: BackgroundTasks,
    completed: bool | None = None,
    category: TaskCategory | None = None,
) -> FileResponse:
    """
    Export tasks as CSV.

    - **status**: Filter by task status (optional).
    - **category**: Filter by task category (optional).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", newline="", encoding="utf-8"
    ) as tmp:
        tmp_path = tmp.name

        file_path = bl.generate_csv_file(
            filename=tmp_path, completed=completed, category=category
        )

        if file_path is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="No tasks found for the selected filters",
            )
        if file_path != tmp_path:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to generate CSV file",
            )

        background_tasks.add_task(os.unlink, tmp_path)

        return FileResponse(
            path=file_path,
            filename=DEFAULT_CSV_FILE,
            media_type="text/csv",
        )


@router.get(
    "/reports",
    summary="Get task reports",
    description="Get statistics about tasks",
    response_description="Task statistics",
)
def get_reports() -> TaskReport:
    """Get statistics about tasks."""
    return bl.generate_report()
