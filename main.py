from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, get_db
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

# Create a session dependency typehint
DbSessionDependency = Annotated[AsyncSession, Depends(get_db)]


@app.get("/api")
async def home():
    return "Welcome to FastAPI based Blog API management system"


@app.get("/health")
async def health_check(db: DbSessionDependency):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        )
    return {"status": "healthy"}
