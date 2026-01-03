import random
from flask import Flask, jsonify
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database import SessionLocal
from models import Post, Comment

app = Flask(__name__)

NUM_POSTS = 50_000

@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()

@app.route("/benchmark/db-test")
def db_test():
    """
    Simulates a heavy-read operation:
    Random Id -> Join Post, User, Comments, Comment.User
    """
    session = SessionLocal()
    
    post_id = random.randint(1, NUM_POSTS)
    
    # Consistent logic with FastAPI: joinedload author + comments + comment author
    stmt = (
        select(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.comments).joinedload(Comment.author)
        )
        .where(Post.id == post_id)
    )
    
    post = session.execute(stmt).unique().scalars().first()
    
    if not post:
        return jsonify({"error": "Post not found"}), 404
        
    return jsonify({
        "post_id": post.id,
        "title": post.title,
        "author": post.author.username,
        "last_updated": post.created_at.isoformat(),
        "comments": [
            {"user": c.author.username, "content": c.content} 
            for c in post.comments
        ]
    })
