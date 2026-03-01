from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def check_all_tables():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
        tables = [row[0] for row in result]
        print(f"Tables found: {tables}")
        
        for table in tables:
            print(f"\n--- Columns in {table} ---")
            col_result = conn.execute(text(f"SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = '{table}';"))
            for row in col_result:
                print(f"Column: {row[0]}, Type: {row[1]}, Max Length: {row[2]}")

if __name__ == "__main__":
    try:
        check_all_tables()
    except Exception as e:
        print(f"Error: {e}")
