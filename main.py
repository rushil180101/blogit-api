from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import engine
from routers import posts, users


@asynccontextmanager
async def lifespan(_app: FastAPI):

    # Pass control over to FastAPI app
    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", app=StaticFiles(directory="static"), name="static")

# Add routes
app.include_router(router=users.router, prefix="/api/users", tags=["users"])
app.include_router(router=posts.router, prefix="/api/posts", tags=["posts"])


@app.get("/api")
async def home():
    return "Welcome to FastAPI based Blog API management system"
