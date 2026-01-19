from typing import List
from fastapi import APIRouter, HTTPException

from . import database
from .models import Task, TaskCreate, TaskUpdate

router = APIRouter()


@router.get("/tasks", response_model=List[Task])
def get_tasks():
    return database.get_all()


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    task = database.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks", response_model=Task, status_code=201)
def create_task(task_in: TaskCreate):
    return database.create(task_in)


@router.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, task_update: TaskUpdate):
    updated_task = database.update(task_id, task_update)
    if not updated_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated_task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    success = database.delete(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return
