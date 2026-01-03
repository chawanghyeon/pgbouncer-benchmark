import asyncio
import io
import time
from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Configuration
DB_URL = "postgresql+asyncpg://postgres:password@localhost:5432/benchmark_db"
NUM_USERS = 10_000
NUM_POSTS = 50_000
NUM_COMMENTS = 100_000
BATCH_SIZE = 1000

fake = Faker()


async def get_engine():
    return create_async_engine(DB_URL, echo=False)


def generate_csv_buffer(data):
    buffer = io.StringIO()
    for row in data:
        # Simple CSV format handled manually to avoid overhead
        # Escape tabs and newlines
        clean_row = [str(x).replace("\t", " ").replace("\n", " ") for x in row]
        buffer.write("\t".join(clean_row) + "\n")
    buffer.seek(0)
    return buffer


async def seed_users(conn):
    print(f"Seeding {NUM_USERS} users...")
    users = []
    for _ in range(NUM_USERS):
        users.append((fake.unique.user_name(), fake.unique.email()))

    # Using raw COPY for maximum speed
    buffer = generate_csv_buffer(users)
    raw_conn = await conn.get_raw_connection()
    await raw_conn.driver_connection.copy_records_to_table(
        "users", records=users, columns=["username", "email"], timeout=30
    )
    print("Users seeded.")


async def seed_posts(conn):
    print(f"Seeding {NUM_POSTS} posts...")
    posts = []
    for _ in range(NUM_POSTS):
        uid = fake.random_int(min=1, max=NUM_USERS)
        posts.append((uid, fake.sentence(), fake.text()))

    raw_conn = await conn.get_raw_connection()
    await raw_conn.driver_connection.copy_records_to_table(
        "posts", records=posts, columns=["user_id", "title", "content"], timeout=60
    )
    print("Posts seeded.")


async def seed_comments(conn):
    print(f"Seeding {NUM_COMMENTS} comments...")
    comments = []
    for _ in range(NUM_COMMENTS):
        uid = fake.random_int(min=1, max=NUM_USERS)
        pid = fake.random_int(min=1, max=NUM_POSTS)
        comments.append((uid, pid, fake.text()))

    raw_conn = await conn.get_raw_connection()
    await raw_conn.driver_connection.copy_records_to_table(
        "comments",
        records=comments,
        columns=["user_id", "post_id", "content"],
        timeout=60,
    )
    print("Comments seeded.")


async def main():
    start_time = time.time()
    engine = await get_engine()

    async with engine.begin() as conn:
        print("Cleaning up existing data...")
        await conn.execute(
            text("TRUNCATE TABLE comments, posts, users RESTART IDENTITY CASCADE")
        )

        await seed_users(conn)
        await seed_posts(conn)
        await seed_comments(conn)

    await engine.dispose()
    print(f"Total Seeding Time: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
