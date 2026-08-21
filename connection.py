import asyncpg
from contextlib import asynccontextmanager

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        host="localhost",
        user="postgres",
        database="Your DataBase name",
        password="Your Password",
        port=5432,
        min_size=1,
        max_size=10
    )
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS customers(
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(200) NOT NULL,
            email VARCHAR(100),
            balance INT DEFAULT 0,
            currency VARCHAR(10) DEFAULT 'USD',
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS transaction(
            id SERIAL PRIMARY KEY,
            amount INT NOT NULL,
            type VARCHAR(10) CHECK(type IN ('income','expense')),
            category VARCHAR(50) DEFAULT 'General',
            description VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            user_id INT REFERENCES customers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS budgets(
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES customers(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            monthly_limit INT NOT NULL,
            UNIQUE(user_id, category)
        );
        """)

@asynccontextmanager
async def get_connection():
    async with pool.acquire() as conn:
        yield conn