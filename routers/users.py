from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from auth import CurrentUser, create_access_token, hash_password, verify_password
from config import settings
from database import get_db
from image_utils import delete_image, process_image
from models import User
from schemas import Token, UserCreate, UserPrivate, UserPublic, UserUpdate

router = APIRouter()

# Create a oauth2 password request form dependency
OAuth2FormDependency = Annotated[OAuth2PasswordRequestForm, Depends()]


# Create a session dependency typehint
DbSessionDependency = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/token",
    response_model=Token,
    status_code=status.HTTP_200_OK,
)
async def get_access_token(form_data: OAuth2FormDependency, db: DbSessionDependency):
    result = await db.execute(select(User).where(User.username == form_data.username))
    existing_user = result.scalars().first()

    if not existing_user or not verify_password(
        plain_text_password=form_data.password,
        hashed_password=existing_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Now username and password are valid, hence, create access token
    access_token = create_access_token(data={"sub": str(existing_user.id)})
    return Token(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserPrivate,
    status_code=status.HTTP_200_OK,
)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.post(
    "",
    response_model=UserPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(user: UserCreate, db: DbSessionDependency):
    # Check for existing user with same username
    result = await db.execute(select(User).where(User.username == user.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user with this username already exists",
        )

    # Check for existing user with same email
    result = await db.execute(select(User).where(User.email == user.email))
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user with this email already exists",
        )

    # Create a new user object
    password_hash = hash_password(password=user.password)
    new_user = User(
        username=user.username, email=user.email, password_hash=password_hash
    )

    # Save to database
    db.add(new_user)  # No need of "await" here because this just adds to the memory
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.get(
    "",
    response_model=List[UserPublic],
    status_code=status.HTTP_200_OK,
)
async def get_users(
    db: DbSessionDependency,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    result = await db.execute(select(User).offset(offset).limit(limit))
    users = result.scalars().all()
    return users


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
)
async def get_user(user_id: int, db: DbSessionDependency):
    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    return existing_user


@router.patch(
    "/{user_id}",
    response_model=UserPrivate,
    status_code=status.HTTP_200_OK,
)
async def update_user_partial(
    user_id: int, user: UserUpdate, current_user: CurrentUser, db: DbSessionDependency
):

    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to update the user",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    if user.username is not None and user.username != existing_user.username:
        result = await db.execute(select(User).where(User.username == user.username))
        existing_user_with_same_username = result.scalars().first()
        if existing_user_with_same_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user with this username already exists",
            )

    if user.email is not None and user.email != existing_user.email:
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user_with_same_email = result.scalars().first()
        if existing_user_with_same_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user with this email already exists",
            )

    udpated_user = user.model_dump(exclude_unset=True)
    for key, value in udpated_user.items():
        setattr(existing_user, key, value)

    await db.commit()
    await db.refresh(existing_user)
    return existing_user


@router.patch(
    "/{user_id}/profile_pic",
    response_model=UserPrivate,
    status_code=status.HTTP_200_OK,
)
async def update_user_profile_pic(
    user_id: int,
    file: UploadFile,  # multi-part form data utilities
    current_user: CurrentUser,
    db: DbSessionDependency,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not allowed to perform profile pic update operation",
        )

    content = await file.read()
    if len(content) > settings.max_profile_pic_image_size_bytes:
        max_allowed_size_mb = settings.max_profile_pic_image_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"file is too large, maximum allowed size is {max_allowed_size_mb}MB"
            ),
        )

    try:
        # Image processing is a CPU-bound task, hence, we run it in a
        # separate thread pool, because, running it here directly will
        # block the event loop and make the API response much slower
        new_filename = await run_in_threadpool(process_image, content)
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="got invalid image file, please upload a valid image (JPEG, PNG)",
        )

    old_filename = current_user.image_file

    current_user.image_file = new_filename
    await db.commit()
    await db.refresh(current_user)

    # We delete the old image after updating the user with new image because
    # if we did vice versa, i.e., delete old image first and then update the
    # new image, then if there is an error while updating new image, the user
    # will be left with no profile pic image at all in our system. But in this
    # case, we might get orphan image files on disk, but atleast user will have
    # an associated profile pic image at any given point of time.
    if old_filename:
        delete_image(old_filename)

    return current_user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(user_id: int, current_user: CurrentUser, db: DbSessionDependency):

    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to delete the user",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    old_filename = existing_user.image_file

    await db.delete(existing_user)
    await db.commit()

    if old_filename is not None:
        delete_image(old_filename)


@router.delete(
    "/{user_id}/profile_pic",
    response_model=UserPrivate,
    status_code=status.HTTP_200_OK,
)
async def delete_user_profile_pic(
    user_id: int,
    current_user: CurrentUser,
    db: DbSessionDependency,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not allowed to perform profile pic delete operation",
        )

    old_filename = current_user.image_file
    if not old_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="profile pic does not exist",
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)
    delete_image(old_filename)
    return current_user
