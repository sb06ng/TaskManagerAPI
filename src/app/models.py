import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.settings import settings
from app.utils import date_utc_validator_factory, ensure_utc

FutureDate = Annotated[datetime, AfterValidator(date_utc_validator_factory())]
UtcDate = Annotated[datetime, AfterValidator(ensure_utc)]


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCategory(str, Enum):
    GENERAL = "General"
    URGENT = "Urgent"
    PERFORMANCE = "Performance"
    PERSONAL = "Personal"
    OTHER = "Other"


class TaskBase(BaseModel):
    """Base model for task with common fields."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_title_length,
        description="Task title",
    )
    description: str = Field(
        ..., max_length=settings.max_description_length, description="Task description"
    )
    due_date: FutureDate = Field(..., description="Task due date")
    category: TaskCategory = TaskCategory.GENERAL
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: list[uuid.UUID] = Field(default_factory=list)


class TaskCreate(TaskBase):
    """Model for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Model for updating an existing task. All fields are optional."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.max_title_length,
        description="Task title",
    )
    description: str | None = Field(
        default=None,
        max_length=settings.max_description_length,
        description="Task description",
    )
    due_date: FutureDate | None = Field(default=None)
    category: TaskCategory | None = Field(default=None)
    priority: TaskPriority | None = Field(default=None)
    is_completed: bool | None = Field(default=None)
    dependencies: list[uuid.UUID] | None = Field(default=None)


class Task(TaskBase):
    """Complete task model with all fields."""

    id: uuid.UUID = Field(..., description="Unique task identifier")
    creation_date: UtcDate = Field(..., description="Task creation timestamp")
    completion_date: UtcDate | None = Field(
        None, description="Task completion timestamp"
    )
    is_completed: bool = Field(False, description="Task completion status")


class TaskReport(BaseModel):
    total_tasks: int
    completed_tasks: int
    avg_completion_time_seconds: float | None
    tasks_by_category: dict[str, int]
    tasks_by_priority: dict[str, int]
