from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    __table_args__ = {"schema": "survey"}
    id = Column(Integer, primary_key=True)
    interviewer_name = Column(String)

def check():
    session = SessionLocal()
    count = session.query(SurveyResponse).count()
    print(f"Total survey responses: {count}")
    session.close()

if __name__ == "__main__":
    try:
        check()
    except Exception as e:
        print(f"Error: {e}")
