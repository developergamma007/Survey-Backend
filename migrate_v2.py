from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def update_tables():
    commands = [
        "ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS dynamic_answers TEXT;",
        "CREATE TABLE IF NOT EXISTS wards (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE, slug VARCHAR(255) UNIQUE);",
        "CREATE TABLE IF NOT EXISTS questions (id SERIAL PRIMARY KEY, ward_id INTEGER REFERENCES wards(id), text TEXT, options TEXT);"
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
                print(f"Executed: {cmd}")
            except Exception as e:
                print(f"Error executing {cmd}: {e}")

if __name__ == "__main__":
    update_tables()
