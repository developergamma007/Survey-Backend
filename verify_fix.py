from sqlalchemy import create_engine, inspect

DATABASE_URL = "postgresql://gamma@localhost:5432/surveydb"
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)
tables = inspector.get_table_names()

if "survey_responses" in tables:
    print("SUCCESS: Table 'survey_responses' found!")
else:
    print("FAILURE: Table 'survey_responses' NOT found.")
    print("Found tables:", tables)
