import json
import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import config
from .models import TaskCreate, TaskUpdate


def _load_json() -> List[dict]:
    """Internal helper to read the file."""
    if not os.path.exists(config.DB_FILE):
        return []
    try:
        with open(config.DB_FILE, "r") as f:
            data = f.read()
            return json.loads(data) if data else []
    except json.JSONDecodeError:
        return []


def _save_json(tasks: List[dict]):
    """Internal helper to write to the file."""
    with open(config.DB_FILE, "w") as f:
        json.dump(tasks, f, indent=4, default=str)


def get_all() -> List[dict]:
    return _load_json()


def get_by_id(task_id: str) -> Optional[dict]:
    tasks = _load_json()
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def create(task_in: TaskCreate) -> dict:
    tasks = _load_json()
    new_task = {
        "id": str(uuid4()),
        "title": task_in.title,
        "description": task_in.description,
        "creation_date": datetime.now(),
        "completion_date": None,
        "due_date": task_in.due_date,
        "is_completed": False,
    }
    tasks.append(new_task)
    _save_json(tasks)
    return new_task


def update(task_id: str, update_data: TaskUpdate) -> Optional[dict]:
    tasks = _load_json()

    # Find the task index
    task_index = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
    if task_index is None:
        return None

    current_task = tasks[task_index]

    # Update fields only if provided
    if update_data.title is not None:
        current_task["title"] = update_data.title
    if update_data.description is not None:
        current_task["description"] = update_data.description
    if update_data.due_date is not None:
        # Pydantic gives us datetime, we store as ISO string in JSON
        current_task["due_date"] = update_data.due_date
    if update_data.is_completed is not None:
        current_task["is_completed"] = update_data.is_completed
        if update_data.is_completed:
            current_task["completion_date"] = datetime.now()
        else:
            current_task["completion_date"] = None

    tasks[task_index] = current_task
    _save_json(tasks)
    return current_task


def delete(task_id: str) -> bool:
    tasks = _load_json()
    initial_count = len(tasks)
    tasks = [t for t in tasks if t["id"] != task_id]

    if len(tasks) == initial_count:
        return False

    _save_json(tasks)
    return True
