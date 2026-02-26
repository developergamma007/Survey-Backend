from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def update_tables():
    commands = [
        "ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS candidate_priority4 VARCHAR(255);",
        "ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS candidate_priority5 VARCHAR(255);"
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
