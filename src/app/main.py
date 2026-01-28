import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import uvicorn
from fastapi import FastAPI, Response
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database import DatabaseError
from app.routes import router
from app.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api_logger")

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
)

app.include_router(router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(f"Request ID: {request_id} Start {request.method} {request.url.path}")

    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request ID: {request_id} Error: {str(e)}")
        raise e

    process_time = time.time() - start_time

    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"[{request_id}] END Status: {response.status_code} | Time: {process_time:.4f}s"
    )

    return response


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, app_dir="app")
