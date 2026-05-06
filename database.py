from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Database service access url/file
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./blog.db"

# Database engine
engine = create_async_engine(
    url=SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Factory to create database sessions
async_session_local = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# Function to yield db session (used by dependency injection mechanism of fastapi)
async def get_db():
    async with async_session_local() as db:
        yield db
