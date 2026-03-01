from datetime import datetime, timedelta
from typing import Any, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

import auth
from config import DATABASE_URL
from fix_booths import migrate as run_migration

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    assembly = Column(Text, nullable=True)
    gba_ward = Column(Text, nullable=True)
    polling_station_name = Column(Text, nullable=True)
    polling_station_number = Column(String(100), nullable=True)
    surveyor_name = Column(Text, nullable=True)
    surveyor_mobile = Column(String(100), nullable=True)

    interviewer_name = Column(Text, nullable=True)
    interviewer_age = Column(String(50), nullable=True)
    interviewer_gender = Column(String(100), nullable=True)
    interviewer_caste = Column(Text, nullable=True)
    interviewer_community = Column(Text, nullable=True)
    interviewer_mobile = Column(String(100), nullable=True)
    interviewer_education = Column(Text, nullable=True)
    interviewer_work = Column(Text, nullable=True)

    q1 = Column(Text, nullable=True)
    q2 = Column(Text, nullable=True)
    q3 = Column(Text, nullable=True)
    q4 = Column(Text, nullable=True)

    candidate_priority1 = Column(Text, nullable=True)
    candidate_priority2 = Column(Text, nullable=True)
    candidate_priority3 = Column(Text, nullable=True)
    candidate_priority4 = Column(Text, nullable=True)
    candidate_priority5 = Column(Text, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    audio_base64 = Column(Text, nullable=True)
    dynamic_answers = Column(Text, nullable=True)  # Store as JSON string

    created_at = Column(DateTime, default=datetime.utcnow)


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    ward_code = Column(String(100), unique=True, index=True, nullable=True)
    ward_name_en = Column(Text, unique=True, index=True)
    ward_name_local = Column(Text, nullable=True)
    
    questions = relationship("Question", back_populates="ward", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id"))
    text = Column(Text)
    options = Column(Text)  # Store as comma-separated or JSON string
    
    ward = relationship("Ward", back_populates="questions")


class Booth(Base):
    __tablename__ = "booths"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id"))
    booth_no = Column(String(100), index=True)
    booth_add_en = Column(Text)
    booth_add_local = Column(Text, nullable=True)
    
    ward = relationship("Ward")


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, index=True)
    ward_code = Column(Text)
    house = Column(Text)
    epic = Column(Text, unique=True, index=True)
    name_en = Column(Text)
    name_kannada = Column(Text)
    gender = Column(Text)
    rel_eng = Column(Text)
    rel_kannada = Column(Text)
    rel_type = Column(Text)


class SurveyCreate(BaseModel):
    assembly: str
    gbaWard: str
    pollingStationName: str
    pollingStationNumber: str
    surveyorName: str
    surveyorMobile: str

    interviewerName: str
    interviewerAge: str
    interviewerGender: str
    interviewerCaste: str
    interviewerCommunity: str
    interviewerMobile: str
    interviewerEducation: str
    interviewerWork: str

    q1: str
    q2: str
    q3: str
    q4: str

    candidatePriority1: str | None = None
    candidatePriority2: str | None = None
    candidatePriority3: str | None = None
    candidatePriority4: str | None = None
    candidatePriority5: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    audio_base64: str | None = None
    dynamicAnswers: str | None = None


class QuestionCreate(BaseModel):
    text: str
    options: List[str]


class WardCreate(BaseModel):
    ward_name_en: str


class BoothCreate(BaseModel):
    ward_id: int
    booth_no: str
    booth_add_en: str
    booth_add_local: str | None = None


class QuestionOut(BaseModel):
    id: int
    text: str
    options: str

    class Config:
        from_attributes = True


class WardOut(BaseModel):
    id: int
    ward_name_en: str | None = None

    class Config:
        from_attributes = True


class VoterSearch(BaseModel):
    id: int | None = None
    ward_code: str | None = None
    house: str | None = None
    epic: str | None = None
    name_en: str | None = None
    name_kannada: str | None = None
    gender: str | None = None
    rel_eng: str | None = None
    rel_kannada: str | None = None
    rel_type: str | None = None

    class Config:
        from_attributes = True


class BoothOut(BaseModel):
    id: int | None = None
    ward_id: int | None = None
    booth_no: str | None = None
    booth_add_en: str | None = None
    booth_add_local: str | None = None

    class Config:
        from_attributes = True


class SurveyOut(BaseModel):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SurveyRead(BaseModel):
    id: int
    assembly: str | None
    gba_ward: str | None
    polling_station_name: str | None
    polling_station_number: str | None
    surveyor_name: str | None
    surveyor_mobile: str | None
    interviewer_name: str | None
    interviewer_age: str | None
    interviewer_gender: str | None
    interviewer_caste: str | None
    interviewer_community: str | None
    interviewer_mobile: str | None
    interviewer_education: str | None
    interviewer_work: str | None
    q1: str | None
    q2: str | None
    q3: str | None
    q4: str | None
    candidate_priority1: str | None
    candidate_priority2: str | None
    candidate_priority3: str | None
    candidate_priority4: str | None
    candidate_priority5: str | None
    latitude: float | None
    longitude: float | None
    audio_base64: str | None
    dynamic_answers: str | None
    created_at: datetime

    class Config:
        from_attributes = True


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def _table_columns(db: Session, table_name: str) -> list[str]:
    result = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"table_name": table_name},
    )
    return [row[0] for row in result]


def _normalize_booth_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "ward_id": row.get("ward_id"),
        "booth_no": row.get("booth_no"),
        "booth_add_en": row.get("booth_add_en") or row.get("booth_add") or row.get("booth_name_en"),
        "booth_add_local": row.get("booth_add_local") or row.get("booth_name_local"),
    }


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    try:
        run_migration()
        init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        print("Application will continue without database, but some endpoints may not work.")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth.authenticate_user(auth.fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/responses", response_model=List[SurveyRead])
def read_surveys(current_user: auth.User = Depends(auth.get_current_user)):
    db: Session = SessionLocal()
    try:
        surveys = db.query(SurveyResponse).order_by(SurveyResponse.created_at.desc()).all()
        return surveys
    finally:
        db.close()


@app.post("/surveys", response_model=SurveyOut)
def create_survey(payload: SurveyCreate):
    db: Session = SessionLocal()
    try:
        survey = SurveyResponse(
            assembly=payload.assembly,
            gba_ward=payload.gbaWard,
            polling_station_name=payload.pollingStationName,
            polling_station_number=payload.pollingStationNumber,
            surveyor_name=payload.surveyorName,
            surveyor_mobile=payload.surveyorMobile,
            interviewer_name=payload.interviewerName,
            interviewer_age=payload.interviewerAge,
            interviewer_gender=payload.interviewerGender,
            interviewer_caste=payload.interviewerCaste,
            interviewer_community=payload.interviewerCommunity,
            interviewer_mobile=payload.interviewerMobile,
            interviewer_education=payload.interviewerEducation,
            interviewer_work=payload.interviewerWork,
            q1=payload.q1,
            q2=payload.q2,
            q3=payload.q3,
            q4=payload.q4,
            candidate_priority1=payload.candidatePriority1 or "",
            candidate_priority2=payload.candidatePriority2 or "",
            candidate_priority3=payload.candidatePriority3 or "",
            candidate_priority4=payload.candidatePriority4 or "",
            candidate_priority5=payload.candidatePriority5 or "",
            latitude=payload.latitude,
            longitude=payload.longitude,
            audio_base64=payload.audio_base64,
            dynamic_answers=payload.dynamicAnswers,
        )
        db.add(survey)
        db.commit()
        db.refresh(survey)
        return survey
    finally:
        db.close()


@app.get("/api/wards", response_model=List[WardOut])
def get_wards():
    """Get all wards from database"""
    db: Session = SessionLocal()
    try:
        wards = db.query(Ward).filter(Ward.ward_name_en != None).all()
        return wards
    finally:
        db.close()


@app.post("/api/wards", response_model=WardOut)
def create_ward(payload: WardCreate):
    db: Session = SessionLocal()
    try:
        ward = Ward(ward_name_en=payload.ward_name_en)
        db.add(ward)
        db.commit()
        db.refresh(ward)
        return ward
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.get("/api/booths", response_model=List[BoothOut])
def get_booths(ward_id: int | None = None):
    """Get all booths with booth_no, optionally filtered by ward_id"""
    db: Session = SessionLocal()
    try:
        booth_columns = set(_table_columns(db, "booths"))
        if not booth_columns:
            return []

        select_cols = ", ".join(f'"{col}"' for col in booth_columns)
        sql = f"SELECT {select_cols} FROM booths"
        params: dict[str, Any] = {}
        if ward_id is not None and "ward_id" in booth_columns:
            sql += ' WHERE "ward_id" = :ward_id'
            params["ward_id"] = ward_id

        rows = db.execute(text(sql), params).mappings().all()
        return [_normalize_booth_row(dict(row)) for row in rows]
    finally:
        db.close()


@app.get("/api/booths/{booth_id}", response_model=BoothOut)
def get_booth(booth_id: int):
    """Get a specific booth by id"""
    db: Session = SessionLocal()
    try:
        booth_columns = set(_table_columns(db, "booths"))
        if "id" not in booth_columns:
            raise HTTPException(status_code=404, detail="Booth not found")

        select_cols = ", ".join(f'"{col}"' for col in booth_columns)
        booth = db.execute(
            text(f'SELECT {select_cols} FROM booths WHERE "id" = :booth_id'),
            {"booth_id": booth_id},
        ).mappings().first()
        if not booth:
            raise HTTPException(status_code=404, detail="Booth not found")
        return _normalize_booth_row(dict(booth))
    finally:
        db.close()


@app.post("/api/booths", response_model=BoothOut)
def create_booth(payload: BoothCreate):
    """Create a new booth"""
    db: Session = SessionLocal()
    try:
        booth_columns = set(_table_columns(db, "booths"))
        if not booth_columns:
            raise HTTPException(status_code=400, detail="booths table not found")

        values: dict[str, Any] = {}
        if "ward_id" in booth_columns:
            values["ward_id"] = payload.ward_id
        if "booth_no" in booth_columns:
            values["booth_no"] = payload.booth_no

        if "booth_add_en" in booth_columns:
            values["booth_add_en"] = payload.booth_add_en
        elif "booth_add" in booth_columns:
            values["booth_add"] = payload.booth_add_en
        elif "booth_name_en" in booth_columns:
            values["booth_name_en"] = payload.booth_add_en

        if "booth_add_local" in booth_columns:
            values["booth_add_local"] = payload.booth_add_local
        elif "booth_name_local" in booth_columns:
            values["booth_name_local"] = payload.booth_add_local

        if not values:
            raise HTTPException(status_code=400, detail="No compatible columns found in booths table")

        cols_sql = ", ".join(f'"{col}"' for col in values)
        vals_sql = ", ".join(f":{col}" for col in values)
        inserted = db.execute(
            text(f"INSERT INTO booths ({cols_sql}) VALUES ({vals_sql}) RETURNING *"),
            values,
        ).mappings().first()
        db.commit()
        if not inserted:
            raise HTTPException(status_code=500, detail="Failed to create booth")
        return _normalize_booth_row(dict(inserted))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.get("/api/wards/{ward_name}/questions", response_model=List[QuestionOut])
def get_ward_questions(ward_name: str):
    db: Session = SessionLocal()
    try:
        ward = db.query(Ward).filter(Ward.ward_name_en == ward_name).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")
        return ward.questions
    finally:
        db.close()


@app.post("/api/wards/{ward_name}/questions")
def update_ward_questions(ward_name: str, questions: List[QuestionCreate]):
    db: Session = SessionLocal()
    try:
        ward = db.query(Ward).filter(Ward.ward_name_en == ward_name).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")
        
        db.query(Question).filter(Question.ward_id == ward.id).delete()
        
        for q in questions:
            new_q = Question(
                ward_id=ward.id,
                text=q.text,
                options=",".join(q.options)
            )
            db.add(new_q)
        
        db.commit()
        return {"message": "Questions updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
@app.get("/api/voters/search", response_model=List[dict[str, Any]])
def search_voters(
    q: str,
    ward_code: str | None = None,
    ward_no: str | None = None,
    ward_id: int | None = None,
):
    """Search voters by name/epic filtered by ward code/no or ward id."""
    db: Session = SessionLocal()
    try:
        voter_columns = _table_columns(db, "voters")
        if not voter_columns:
            return []
        searchable_columns = [col for col in ["name_en", "name_kannada", "epic"] if col in voter_columns]
        if not searchable_columns:
            raise HTTPException(status_code=500, detail="No searchable voter columns found")

        select_cols = ", ".join(f'"{col}"' for col in voter_columns)
        search_clause = " OR ".join(f'"{col}" ILIKE :pattern' for col in searchable_columns)
        sql = f"SELECT {select_cols} FROM voters WHERE ({search_clause})"
        params: dict[str, Any] = {"pattern": f"%{q}%"}

        requested_ward_text = (ward_code or ward_no or "").strip()

        # Direct ward_id filtering if voters table has numeric ward_id.
        if ward_id is not None and "ward_id" in voter_columns:
            sql += ' AND "ward_id" = :ward_id'
            params["ward_id"] = ward_id
        else:
            # Resolve ward_id -> ward_code when possible.
            if not requested_ward_text and ward_id is not None:
                ward_columns = set(_table_columns(db, "wards"))
                if "id" in ward_columns and "ward_code" in ward_columns:
                    ward_code_value = db.execute(
                        text('SELECT "ward_code" FROM wards WHERE "id" = :ward_id'),
                        {"ward_id": ward_id},
                    ).scalar()
                    if ward_code_value:
                        requested_ward_text = str(ward_code_value).strip()

            # Text ward filter against common voter column names.
            if requested_ward_text:
                if "ward_code" in voter_columns:
                    sql += ' AND "ward_code" = :ward_text'
                    params["ward_text"] = requested_ward_text
                elif "ward_no" in voter_columns:
                    sql += ' AND "ward_no" = :ward_text'
                    params["ward_text"] = requested_ward_text

        sql += " LIMIT 10"
        results = db.execute(text(sql), params).mappings().all()
        return [dict(row) for row in results]
    finally:
        db.close()
