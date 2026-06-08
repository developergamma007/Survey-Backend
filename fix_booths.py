from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))]
        survey_tables = [row[0] for row in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='survey';"))]

    commands = []

    # 1. Survey Responses Migrations
    if 'survey_responses' in survey_tables:
        cols = get_columns('survey_responses', schema='survey')
        text_cols = [
            'assembly', 'gba_ward', 'polling_station_name', 'surveyor_name',
            'interviewer_name', 'interviewer_caste', 'interviewer_community',
            'interviewer_education', 'interviewer_work', 'q1', 'q2', 'q3', 'q4',
            'candidate_priority1', 'candidate_priority2', 'candidate_priority3',
            'candidate_priority4', 'candidate_priority5'
        ]
        for col in text_cols:
            if col in cols:
                commands.append(f"ALTER TABLE survey.survey_responses ALTER COLUMN {col} TYPE TEXT;")
        
        # Ensure mobile/number/age fields are at least 100
        for col in ['polling_station_number', 'surveyor_mobile', 'interviewer_mobile']:
            if col in cols:
                commands.append(f"ALTER TABLE survey.survey_responses ALTER COLUMN {col} TYPE VARCHAR(100);")
        if 'interviewer_age' in cols:
            commands.append("ALTER TABLE survey.survey_responses ALTER COLUMN interviewer_age TYPE VARCHAR(50);")

    # 2. Wards Migrations
    if 'wards' in tables:
        cols = get_columns('wards')
        if 'ward_code' not in cols:
            commands.append("ALTER TABLE wards ADD COLUMN ward_code VARCHAR(100) UNIQUE;")
        commands.append("ALTER TABLE wards ALTER COLUMN ward_name_en TYPE TEXT;")
        commands.append("ALTER TABLE wards ALTER COLUMN ward_name_local TYPE TEXT;")

    # 3. Booths Migrations
    if 'booths' in tables:
        cols = get_columns('booths')
        # Handle booth_add_en/local
        if 'booth_add_en' in cols:
            commands.append("ALTER TABLE booths ALTER COLUMN booth_add_en TYPE TEXT;")
        if 'booth_add_local' in cols:
            commands.append("ALTER TABLE booths ALTER COLUMN booth_add_local TYPE TEXT;")
        
        # Cleanup extra columns
        commands.append("ALTER TABLE booths DROP COLUMN IF EXISTS booth_name_en;")
        commands.append("ALTER TABLE booths DROP COLUMN IF EXISTS booth_name_local;")
        
        # Requirements
        commands.append("ALTER TABLE booths ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;")
        commands.append("ALTER TABLE booths ADD COLUMN IF NOT EXISTS ward_id INTEGER REFERENCES wards(id);")
        
        if 'ward_code' in cols:
            commands.append("UPDATE booths b SET ward_id = w.id FROM wards w WHERE b.ward_code = w.ward_code AND b.ward_id IS NULL;")
        
        commands.append("ALTER TABLE booths ALTER COLUMN booth_no TYPE VARCHAR(100);")

    # 4. Voters Migrations
    if 'voters' in tables:
        cols = get_columns('voters')
        voter_text_cols = [
            "ward_code", "house", "epic", "name_en", "name_kannada", 
            "gender", "rel_eng", "rel_kannada", "rel_type"
        ]
        for col in voter_text_cols:
            if col in cols:
                commands.append(f"ALTER TABLE voters ALTER COLUMN {col} TYPE TEXT;")

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

def get_columns(table_name, schema="public"):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table_name;"
            ),
            {"schema": schema, "table_name": table_name},
        )
        return [row[0] for row in result]

if __name__ == "__main__":
    migrate()
