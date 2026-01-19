# main.py
import uvicorn
from fastapi import FastAPI
import config
from app.routes import router

app = FastAPI(title=config.API_TITLE)

# Include the routes from our app folder
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
