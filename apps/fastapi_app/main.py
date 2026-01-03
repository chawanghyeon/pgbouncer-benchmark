import random
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload


from database import get_db
from models import Post, Comment

app = FastAPI()

# Configured in seed.py
NUM_POSTS = 50_000


@app.get("/benchmark/db-test")
async def db_test(db: AsyncSession = Depends(get_db)):
    """
    Simulates a heavy-read operation:
    1. Selects a random post.
    2. JOINs with the User table (Author).
    3. JOINs with the Comment table.
    """
    post_id = random.randint(1, NUM_POSTS)

    # Using joinedload to force SQL JOINs
    stmt = (
        select(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.comments).joinedload(Comment.author),
        )
        .where(Post.id == post_id)
    )

    result = await db.execute(stmt)
    # unique() is required when using joinedload with 1:N relationships in asyncio/modern SQLAlchemy
    post = result.unique().scalars().first()

    if not post:
        # In case of gaps or sync issues, though seed is sequential types
        raise HTTPException(status_code=404, detail="Post not found")

    return {
        "post_id": post.id,
        "title": post.title,
        "author": post.author.username,
        "last_updated": post.created_at,
        "comments": [
            {"user": c.author.username, "content": c.content} for c in post.comments
        ],  # Accessing comments triggers lazy load if not eager loaded, but we eager loaded
    }
