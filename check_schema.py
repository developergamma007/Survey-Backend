from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def check_columns():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name = 'booths';"))
        for row in result:
            print(f"Column: {row[0]}, Length: {row[1]}")

if __name__ == "__main__":
    try:
        check_columns()
    except Exception as e:
        print(f"Error: {e}")
