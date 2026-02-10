from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_file: str = "tasks.json"
    api_title: str = "Task Management API"
    api_description: str = """
Task Management API allows you to:
* Create tasks with title, description, and due date
* Retrieve all tasks or a specific task
* Update task details and completion status
* Delete tasks
"""
    log_level: str = "INFO"
    max_title_length: int = 200
    max_description_length: int = 2000
    api_version: str = "1.0.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
