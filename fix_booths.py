from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        # Check if booths table exists
        booths_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'booths');")).scalar()
        # Check if voters table exists
        voters_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'voters');")).scalar()

    commands = []
    
    if booths_exists:
        commands.extend([
            # 1. Add id column to booths if it doesn't exist
            "ALTER TABLE booths ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;",
            
            # 2. Add ward_id column to booths if it doesn't exist
            "ALTER TABLE booths ADD COLUMN IF NOT EXISTS ward_id INTEGER REFERENCES wards(id);",
            
            # 3. Handle booth_add_en -> booth_name_en rename and size
            "ALTER TABLE booths ALTER COLUMN booth_add_en TYPE VARCHAR(500);" if "booth_add_en" in get_columns("booths") else "",
            "ALTER TABLE booths RENAME COLUMN booth_add_en TO booth_name_en;" if "booth_add_en" in get_columns("booths") else "",
            
            # 4. Handle booth_add_local -> booth_name_local rename and size
            "ALTER TABLE booths ALTER COLUMN booth_add_local TYPE VARCHAR(500);" if "booth_add_local" in get_columns("booths") else "",
            "ALTER TABLE booths RENAME COLUMN booth_add_local TO booth_name_local;" if "booth_add_local" in get_columns("booths") else "",
            
            # 5. Ensure booth_name_* already in place are 500
            "ALTER TABLE booths ALTER COLUMN booth_name_en TYPE VARCHAR(500);" if "booth_name_en" in get_columns("booths") else "",
            "ALTER TABLE booths ALTER COLUMN booth_name_local TYPE VARCHAR(500);" if "booth_name_local" in get_columns("booths") else "",
            
            # 6. Update ward_id based on ward_code
            "UPDATE booths b SET ward_id = w.id FROM wards w WHERE b.ward_code = w.ward_code AND b.ward_id IS NULL;" if "ward_code" in get_columns("booths") else "",
            
            # 7. Ensure booth_no is compatible with String(50)
            "ALTER TABLE booths ALTER COLUMN booth_no TYPE VARCHAR(50);" 
        ])

    if voters_exists:
        voter_cols = get_columns("voters")
        voter_alterations = [
            ("ward_code", "TEXT"),
            ("house", "TEXT"),
            ("epic", "TEXT"),
            ("name_en", "TEXT"),
            ("name_kannada", "TEXT"),
            ("gender", "TEXT"),
            ("rel_eng", "TEXT"),
            ("rel_kannada", "TEXT"),
            ("rel_type", "TEXT")
        ]
        for col, new_type in voter_alterations:
            if col in voter_cols:
                commands.append(f"ALTER TABLE voters ALTER COLUMN {col} TYPE {new_type};")

    if not commands:
        return
    
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
