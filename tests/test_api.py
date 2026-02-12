from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from app.models import Task, TaskPriority, TaskReport, TaskUpdate


def test_create_task(client: TestClient, sample_task_data: Task) -> None:
    response = client.post(
        "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
    )
    assert response.status_code == HTTPStatus.CREATED
    data = Task(**response.json())
    assert data.title == sample_task_data.title
    assert data.id is not None
    assert data.creation_date is not None


def test_get_tasks_empty(client: TestClient) -> None:
    response = client.get("/tasks")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data == []


def test_get_task_by_id(client: TestClient, sample_task_data: Task) -> None:
    create_res = client.post(
        "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
    )
    task = Task(**create_res.json())

    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == HTTPStatus.OK
    fetched_task = Task(**response.json())
    assert fetched_task.id == task.id


def test_update_task_completion(client: TestClient, sample_task_data: Task) -> None:
    task = Task(
        **client.post(
            "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
        ).json()
    )
    assert task.is_completed is False
    update_data = TaskUpdate(is_completed=True)
    response = client.put(
        f"/tasks/{task.id}",
        json=update_data.model_dump(exclude_unset=True, mode="json"),
    )
    assert response.status_code == HTTPStatus.OK
    response_task = Task(**response.json())
    assert response_task.is_completed is True
    assert response_task.completion_date is not None


def test_delete_task(client: TestClient, sample_task_data: Task) -> None:
    task = Task(
        **client.post(
            "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
        ).json()
    )
    delete_res = client.delete(f"/tasks/{task.id}")
    assert delete_res.status_code == HTTPStatus.NO_CONTENT
    get_res = client.get(f"/tasks/{task.id}")
    assert get_res.status_code == HTTPStatus.NOT_FOUND


def test_get_reports(client: TestClient, sample_task_data: Task) -> None:
    client.post(
        "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
    )

    response = client.get("/reports")
    assert response.status_code == HTTPStatus.OK
    data = TaskReport(**response.json())
    assert data.total_tasks > 0
    assert isinstance(data.completed_tasks, int)


@pytest.mark.parametrize("priority_enum", list(TaskPriority))
def test_filter_by_priority(
    client: TestClient, sample_task_data: Task, priority_enum: TaskPriority
) -> None:
    sample_task_data.priority = priority_enum
    client.post(
        "/tasks", json=sample_task_data.model_dump(exclude_unset=True, mode="json")
    )

    response = client.get(f"/tasks?priority={priority_enum.value}")
    assert response.status_code == HTTPStatus.OK
    tasks = [Task(**t) for t in response.json()]
    assert len(tasks) > 0
    assert all(t.priority == priority_enum for t in tasks)
