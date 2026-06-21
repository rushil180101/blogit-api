from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

# Database engine
engine = create_async_engine(url=settings.database_url)

# Factory to create database sessions
async_session_local = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# Function to yield db session (used by dependency injection mechanism of fastapi)
async def get_db():
    async with async_session_local() as db:
        yield db
