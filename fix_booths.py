import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gamma@localhost:5432/surveydb",
)

engine = create_engine(DATABASE_URL)

def migrate():
    commands = [
        # 1. Add id column to booths if it doesn't exist
        "ALTER TABLE booths ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;",
        
        # 2. Add ward_id column to booths if it doesn't exist
        "ALTER TABLE booths ADD COLUMN IF NOT EXISTS ward_id INTEGER REFERENCES wards(id);",
        
        # 3. Rename columns to match main.py model
        "ALTER TABLE booths RENAME COLUMN booth_add_en TO booth_name_en;" if "booth_add_en" in get_columns("booths") else "",
        "ALTER TABLE booths RENAME COLUMN booth_add_local TO booth_name_local;" if "booth_add_local" in get_columns("booths") else "",
        
        # 4. Update ward_id based on ward_code
        "UPDATE booths b SET ward_id = w.id FROM wards w WHERE b.ward_code = w.ward_code AND b.ward_id IS NULL;",
        
        # 5. Ensure booth_no is compatible with String(50) - it's currently integer but SQLAlchemy expects String
        # We can leave it as integer in DB, SQLAlchemy often handlesint -> str casting for String columns, 
        # but let's make it varchar(50) to be safe and match the model's intended flexibility.
        "ALTER TABLE booths ALTER COLUMN booth_no TYPE VARCHAR(50);" 
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            if not cmd: continue
            try:
                conn.execute(text(cmd))
                conn.commit()
                print(f"Executed: {cmd}")
            except Exception as e:
                print(f"Error executing {cmd}: {e}")
                conn.rollback()

def get_columns(table_name):
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';"))
        return [row[0] for row in result]

if __name__ == "__main__":
    migrate()
