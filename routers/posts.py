from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Post, User
from schemas import PostCreate, PostResponse, PostUpdate

router = APIRouter()


# Create a session dependency typehint
DbSessionDependency = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(post: PostCreate, db: DbSessionDependency):
    result = await db.execute(select(User).where(User.id == post.user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    new_post = Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id,
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(
        new_post, attribute_names=["author"]
    )  # "attribute_names" allows to also load relationships
    return new_post


@router.get(
    "",
    response_model=List[PostResponse],
    status_code=status.HTTP_200_OK,
)
async def get_posts(
    db: DbSessionDependency,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .offset(offset)
        .limit(limit)
        .order_by(Post.date_posted.desc())
    )
    posts = result.scalars().all()
    return posts


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
async def get_post_by_id(post_id: int, db: DbSessionDependency):
    result = await db.execute(
        select(Post).options(selectinload(Post.author)).where(Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        )
    return post


@router.get(
    "/user/{user_id}",
    response_model=List[PostResponse],
    status_code=status.HTTP_200_OK,
)
async def get_posts_by_user(user_id: int, db: DbSessionDependency):
    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .where(Post.user_id == user_id)
        .order_by(Post.date_posted.desc())
    )
    posts = result.scalars().all()
    return posts


@router.put(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
async def update_post_full(post_id: int, post: PostCreate, db: DbSessionDependency):
    result = await db.execute(select(Post).where(Post.id == post_id))
    existing_post = result.scalars().first()
    if not existing_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        )

    existing_user_id = existing_post.user_id
    user_id_in_request = post.user_id
    if existing_user_id != user_id_in_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot change user id while upating a post",
        )

    existing_post.title = post.title
    existing_post.content = post.content
    existing_post.user_id = post.user_id

    await db.commit()
    await db.refresh(existing_post, attribute_names=["author"])
    return existing_post


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
async def update_post_partial(post_id: int, post: PostUpdate, db: DbSessionDependency):
    result = await db.execute(select(Post).where(Post.id == post_id))
    existing_post = result.scalars().first()
    if not existing_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        )

    updated_post = post.model_dump(
        exclude_unset=True
    )  # Skips fields that were not sent in the patch request
    for key, value in updated_post.items():
        setattr(existing_post, key, value)

    await db.commit()
    await db.refresh(existing_post, attribute_names=["author"])
    return existing_post


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_post_by_id(post_id: int, db: DbSessionDependency):
    result = await db.execute(select(Post).where(Post.id == post_id))
    existing_post = result.scalars().first()
    if not existing_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        )

    await db.delete(existing_post)
    await db.commit()
