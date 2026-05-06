from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import engine
from models import Base
from routers import posts, users

# Create an async lifespan for FastAPI app
# - Before initializing the FastAPI app, load the async db tables
# - Pass over the control to FastAPI app (yield)
# - Close the async db connections properly


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Pass control over to FastAPI app
    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# Mount static and media files
app.mount("/static", app=StaticFiles(directory="static"), name="static")
app.mount("/media", app=StaticFiles(directory="media"), name="media")

# Add routes
app.include_router(router=users.router, prefix="/api/users", tags=["users"])
app.include_router(router=posts.router, prefix="/api/posts", tags=["posts"])


@app.get("/api")
async def home():
    return "Welcome to FastAPI based Blog API management system"


# Start from Part 10 - Authentication (33:00)
# System Design - Video 3
