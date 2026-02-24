import os
from sqlalchemy import create_engine, text

print("Testing connection...")

# 1. Try default credentials
try:
    url = "postgresql://postgres:postgres@localhost:5432/surveydb"
    engine = create_engine(url)
    with engine.connect() as conn:
        print("Success with postgres:postgres")
except Exception as e:
    print(f"Failed with postgres:postgres: {e}")

# 2. Try gamma user (local system user)
try:
    url = "postgresql://gamma@localhost:5432/surveydb"
    engine = create_engine(url)
    with engine.connect() as conn:
        print("Success with gamma@localhost")
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        print("Tables found:", [row[0] for row in result])
except Exception as e:
    print(f"Failed with gamma@localhost: {e}")
