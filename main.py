import os
import re
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, or_, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, defer, relationship, sessionmaker

import auth
import form_config
import s3_storage
from config import DATABASE_URL, MAX_AUDIO_UPLOAD_BYTES
from fix_booths import migrate as run_migration

_MOBILE_DIGITS_RE = re.compile(r"^\d{10}$")


def _normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if not _MOBILE_DIGITS_RE.match(digits):
        raise ValueError("Mobile number must be exactly 10 digits")
    return digits

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    __table_args__ = {"schema": "survey"}

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
    audio_url = Column(Text, nullable=True)  # S3 object key
    dynamic_answers = Column(Text, nullable=True)  # Store as JSON string

    created_at = Column(DateTime, default=datetime.utcnow)


class Assembly(Base):
    __tablename__ = "assembly"

    assembly_no = Column(Integer, primary_key=True, index=True)
    assembly_name_en = Column(Text, nullable=True)
    assembly_name_local = Column(Text, nullable=True)


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    ward_code = Column(String(100), unique=True, index=True, nullable=True)
    ward_name_en = Column(Text, unique=True, index=True)
    ward_name_local = Column(Text, nullable=True)
    assembly_no = Column(Integer, nullable=True, index=True)
    
    questions = relationship(
        "Question",
        back_populates="ward",
        cascade="all, delete-orphan",
        foreign_keys="Question.ward_id",
        primaryjoin="Ward.id == Question.ward_id",
    )


class Question(Base):
    __tablename__ = "survey_questions"
    __table_args__ = {"schema": "survey"}

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id"))
    text = Column(Text)
    options = Column(Text)  # Store as comma-separated or JSON string

    ward = relationship(
        "Ward",
        back_populates="questions",
        foreign_keys=[ward_id],
    )


class Booth(Base):
    __tablename__ = "booths"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id"))
    booth_no = Column(String(100), index=True)
    booth_add_en = Column(Text)
    booth_add_local = Column(Text, nullable=True)
    
    ward = relationship("Ward")


class SurveyFormConfigRow(Base):
    __tablename__ = "survey_form_config"
    __table_args__ = {"schema": "survey"}

    id = Column(Integer, primary_key=True)
    config_json = Column(Text, nullable=False)


class Voter(Base):
    """Maps to public.voters — production table has no numeric id column."""

    __tablename__ = "voters"

    epic = Column(Text, primary_key=True)
    ward_code = Column(Text)
    house = Column(Text)
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
    audioKey: str | None = None
    dynamicAnswers: str | None = None

    @field_validator("surveyorMobile", "interviewerMobile", mode="before")
    @classmethod
    def validate_mobile_fields(cls, value):
        if value is None:
            return ""
        return _normalize_mobile(str(value))


class QuestionCreate(BaseModel):
    text: str
    options: str


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


class AssemblyOut(BaseModel):
    assembly_no: int
    assembly_name_en: str | None = None
    assembly_name_local: str | None = None

    class Config:
        from_attributes = True


class WardOut(BaseModel):
    id: int
    ward_name_en: str | None = None
    ward_name_local: str | None = None
    assembly_no: int | None = None

    class Config:
        from_attributes = True


class VoterSearch(BaseModel):
    name_en: str
    epic: str | None = None
    house: str | None = None
    name_kannada: str | None = None
    gender: str | None = None
    age: str | None = None
    mobile: str | None = None
    rel_eng: str | None = None
    rel_kannada: str | None = None
    rel_type: str | None = None
    ward_code: str | None = None
    address_en: str | None = None
    address_local: str | None = None
    sl: str | None = None
    booth_no: str | None = None
    caste: str | None = None
    religion: str | None = None
    education: str | None = None

    class Config:
        from_attributes = True


_VOTER_SEARCH_FIELDS = (
    "name_en",
    "epic",
    "house",
    "name_kannada",
    "gender",
    "age",
    "mobile",
    "rel_eng",
    "rel_kannada",
    "rel_type",
    "ward_code",
    "address_en",
    "address_local",
    "sl",
    "sl_no",
    "booth_no",
    "booth",
    "caste",
    "religion",
    "education",
)


def _voter_table_columns(db: Session) -> set[str]:
    rows = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'voters'"
        )
    ).scalars().all()
    return set(rows)


class BoothOut(BaseModel):
    id: int
    ward_id: int
    booth_no: str
    booth_add_en: str
    booth_add_local: str | None

    class Config:
        from_attributes = True


class SurveyOut(BaseModel):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SurveyListRead(BaseModel):
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
    audio_url: str | None = None
    has_audio: bool = False
    audio_link: str | None = None
    dynamic_answers: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AudioPlaybackOut(BaseModel):
    url: str
    source: str


class AudioUploadOut(BaseModel):
    audioKey: str


class FormConfigOut(BaseModel):
    surveyorFields: dict[str, bool]
    voterFields: dict[str, bool]
    enableVoterSearch: bool
    manualEntryWhenApiEmpty: bool


class FormConfigUpdate(BaseModel):
    surveyorFields: dict[str, bool] | None = None
    voterFields: dict[str, bool] | None = None
    enableVoterSearch: bool | None = None
    manualEntryWhenApiEmpty: bool | None = None


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db_startup_enabled() -> bool:
    return os.getenv("RUN_DB_MIGRATIONS", "true").lower() not in ("0", "false", "no")


def _ensure_audio_url_column() -> None:
    """Idempotent schema patch — safe even when RUN_DB_MIGRATIONS=false."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE survey.survey_responses ADD COLUMN IF NOT EXISTS audio_url TEXT;")
            )
    except Exception as e:
        print(f"Warning: Could not ensure audio_url column: {e}")


def _ensure_survey_user_profile_columns() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE survey.survey_users ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);")
            )
            conn.execute(
                text("ALTER TABLE survey.survey_users ADD COLUMN IF NOT EXISTS mobile VARCHAR(32);")
            )
    except Exception as e:
        print(f"Warning: Could not ensure survey_users profile columns: {e}")


def _ensure_form_config_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS survey.survey_form_config (
                        id INTEGER PRIMARY KEY,
                        config_json TEXT NOT NULL
                    );
                    """
                )
            )
            row = conn.execute(text("SELECT id FROM survey.survey_form_config WHERE id = 1")).first()
            if not row:
                conn.execute(
                    text("INSERT INTO survey.survey_form_config (id, config_json) VALUES (1, :cfg)"),
                    {"cfg": form_config.dump_form_config_json(form_config.DEFAULT_FORM_CONFIG)},
                )
    except Exception as e:
        print(f"Warning: Could not ensure survey_form_config table: {e}")


def _load_form_config(db: Session) -> dict:
    row = db.query(SurveyFormConfigRow).filter(SurveyFormConfigRow.id == 1).first()
    if not row:
        return form_config.normalize_form_config(None)
    return form_config.parse_form_config_json(row.config_json)


@app.on_event("startup")
def on_startup() -> None:
    _ensure_audio_url_column()
    _ensure_survey_user_profile_columns()
    _ensure_form_config_table()
    if not _db_startup_enabled():
        print("[startup] RUN_DB_MIGRATIONS=false — using existing remote schema (no local migrate/create).")
        return
    try:
        run_migration()
        init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        print("Application will continue without database, but some endpoints may not work.")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


async def _issue_access_token(form_data: OAuth2PasswordRequestForm) -> auth.Token:
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


@app.post("/token", response_model=auth.Token)
@app.post("/api/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return await _issue_access_token(form_data)


@app.get("/api/me", response_model=auth.UserProfile)
def read_current_user_profile(current_user: auth.User = Depends(auth.get_current_user)):
    profile = auth.get_user_profile(current_user.username)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile


class SurveyorLoginIn(BaseModel):
    display_name: str
    mobile: str


@app.post("/api/surveyor/login", response_model=auth.Token)
def surveyor_login(payload: SurveyorLoginIn):
    if auth.is_blocked_surveyor_identity(payload.display_name, payload.mobile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin credentials cannot be used for field surveyor sign-in",
        )
    user = auth.get_or_create_surveyor(payload.display_name, payload.mobile)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid surveyor name and 10-digit number",
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


class SurveyUserListItem(BaseModel):
    id: int
    username: str
    display_name: str
    mobile: str
    created_at: datetime
    disabled: bool


@app.get("/api/survey-users", response_model=List[SurveyUserListItem])
def list_survey_users(current_user: auth.User = Depends(auth.require_responses_admin)):
    db = auth.AuthSessionLocal()
    try:
        rows = (
            db.query(auth.SurveyUser)
            .order_by(auth.SurveyUser.created_at.desc())
            .all()
        )
        result: List[SurveyUserListItem] = []
        for row in rows:
            if not auth.is_listable_surveyor_user(row.username, row.display_name, row.mobile):
                continue
            result.append(
                SurveyUserListItem(
                    id=row.id,
                    username=row.username,
                    display_name=auth.normalize_name(row.display_name or row.username),
                    mobile=auth.normalize_mobile(row.mobile or ""),
                    created_at=row.created_at,
                    disabled=bool(row.disabled),
                )
            )
        return result
    finally:
        db.close()


def _survey_has_audio_expr():
    return or_(
        SurveyResponse.audio_url.isnot(None),
        func.coalesce(func.length(SurveyResponse.audio_base64), 0) > 50,
    )


def _resolve_audio_link(survey: SurveyResponse) -> str | None:
    if not survey.audio_url:
        return None
    try:
        return s3_storage.get_playback_url(survey.audio_url)
    except Exception:
        return None


def _to_survey_list_item(survey: SurveyResponse, has_audio: bool) -> SurveyListRead:
    return SurveyListRead(
        id=survey.id,
        assembly=survey.assembly,
        gba_ward=survey.gba_ward,
        polling_station_name=survey.polling_station_name,
        polling_station_number=survey.polling_station_number,
        surveyor_name=survey.surveyor_name,
        surveyor_mobile=survey.surveyor_mobile,
        interviewer_name=survey.interviewer_name,
        interviewer_age=survey.interviewer_age,
        interviewer_gender=survey.interviewer_gender,
        interviewer_caste=survey.interviewer_caste,
        interviewer_community=survey.interviewer_community,
        interviewer_mobile=survey.interviewer_mobile,
        interviewer_education=survey.interviewer_education,
        interviewer_work=survey.interviewer_work,
        q1=survey.q1,
        q2=survey.q2,
        q3=survey.q3,
        q4=survey.q4,
        candidate_priority1=survey.candidate_priority1,
        candidate_priority2=survey.candidate_priority2,
        candidate_priority3=survey.candidate_priority3,
        candidate_priority4=survey.candidate_priority4,
        candidate_priority5=survey.candidate_priority5,
        latitude=survey.latitude,
        longitude=survey.longitude,
        audio_url=survey.audio_url,
        has_audio=has_audio,
        audio_link=_resolve_audio_link(survey) if has_audio else None,
        dynamic_answers=survey.dynamic_answers,
        created_at=survey.created_at,
    )


@app.get("/api/responses", response_model=List[SurveyListRead])
def read_surveys(current_user: auth.User = Depends(auth.require_responses_admin)):
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(SurveyResponse, _survey_has_audio_expr().label("has_audio"))
            .options(defer(SurveyResponse.audio_base64))
            .order_by(SurveyResponse.created_at.desc())
            .all()
        )
        return [_to_survey_list_item(survey, bool(has_audio)) for survey, has_audio in rows]
    finally:
        db.close()


@app.get("/api/responses/{survey_id}/audio", response_model=AudioPlaybackOut)
def get_response_audio(
    survey_id: int,
    current_user: auth.User = Depends(auth.require_responses_admin),
):
    db: Session = SessionLocal()
    try:
        survey = db.query(SurveyResponse).filter(SurveyResponse.id == survey_id).first()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        if survey.audio_url:
            try:
                return AudioPlaybackOut(
                    url=s3_storage.get_playback_url(survey.audio_url),
                    source="s3",
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not generate audio URL: {exc}") from exc

        if survey.audio_base64 and len(survey.audio_base64.strip()) > 50:
            return AudioPlaybackOut(
                url=s3_storage.to_data_url(survey.audio_base64),
                source="legacy",
            )

        raise HTTPException(status_code=404, detail="No audio for this survey")
    finally:
        db.close()


@app.get("/api/survey-form-config", response_model=FormConfigOut)
def get_survey_form_config():
    db: Session = SessionLocal()
    try:
        cfg = _load_form_config(db)
        return FormConfigOut(**cfg)
    finally:
        db.close()


@app.put("/api/survey-form-config", response_model=FormConfigOut)
def update_survey_form_config(
    payload: FormConfigUpdate,
    current_user: auth.User = Depends(auth.require_responses_admin),
):
    db: Session = SessionLocal()
    try:
        row = db.query(SurveyFormConfigRow).filter(SurveyFormConfigRow.id == 1).first()
        current = _load_form_config(db)
        if payload.surveyorFields is not None:
            current["surveyorFields"].update(payload.surveyorFields)
        if payload.voterFields is not None:
            current["voterFields"].update(payload.voterFields)
        if payload.enableVoterSearch is not None:
            current["enableVoterSearch"] = payload.enableVoterSearch
        if payload.manualEntryWhenApiEmpty is not None:
            current["manualEntryWhenApiEmpty"] = payload.manualEntryWhenApiEmpty
        normalized = form_config.normalize_form_config(current)
        serialized = form_config.dump_form_config_json(normalized)
        if row:
            row.config_json = serialized
        else:
            db.add(SurveyFormConfigRow(id=1, config_json=serialized))
        db.commit()
        return FormConfigOut(**normalized)
    finally:
        db.close()


@app.post("/api/surveys/upload-audio", response_model=AudioUploadOut)
async def upload_survey_audio_file(
    audio: UploadFile = File(...),
    current_user: auth.User | None = Depends(auth.get_optional_user),
):
    if current_user and auth.is_submit_blocked_username(current_user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot submit survey responses.",
        )

    content = await audio.read()
    if len(content) < 50:
        raise HTTPException(status_code=400, detail="Audio file is too small")
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        limit_mb = MAX_AUDIO_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file is too large. Maximum allowed size is {limit_mb:.0f} MB.",
        )

    content_type = (audio.content_type or "audio/m4a").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        content_type = "audio/m4a"

    if not s3_storage.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Audio upload requires S3 configuration on the server.",
        )

    try:
        audio_key = s3_storage.upload_survey_audio_bytes(content, content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload audio: {exc}",
        ) from exc

    return AudioUploadOut(audioKey=audio_key)


@app.post("/surveys", response_model=SurveyOut)
async def create_survey(
    payload: SurveyCreate,
    current_user: auth.User | None = Depends(auth.get_optional_user),
):
    if current_user and auth.is_submit_blocked_username(current_user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot submit survey responses.",
        )

    audio_url: str | None = None
    audio_base64: str | None = payload.audio_base64

    if payload.audioKey and payload.audioKey.strip():
        audio_url = payload.audioKey.strip()
        audio_base64 = None
    elif payload.audio_base64 and payload.audio_base64.strip():
        if s3_storage.is_configured():
            try:
                audio_url = s3_storage.upload_survey_audio(payload.audio_base64)
                audio_base64 = None
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload audio to S3: {exc}",
                ) from exc
        else:
            print("[survey] S3 not configured — storing audio as base64 fallback.")

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
            audio_base64=audio_base64,
            audio_url=audio_url,
            dynamic_answers=payload.dynamicAnswers,
        )
        db.add(survey)
        db.commit()
        db.refresh(survey)
        return survey
    finally:
        db.close()


@app.get("/api/assemblies", response_model=List[AssemblyOut])
def get_assemblies():
    """Get all assemblies from database."""
    db: Session = SessionLocal()
    try:
        return (
            db.query(Assembly)
            .filter(Assembly.assembly_name_en.isnot(None))
            .order_by(Assembly.assembly_name_en)
            .all()
        )
    finally:
        db.close()


@app.get("/api/wards", response_model=List[WardOut])
def get_wards(assembly_no: int | None = None):
    """Get wards, optionally filtered by assembly_no."""
    db: Session = SessionLocal()
    try:
        query = db.query(Ward).filter(Ward.ward_name_en.isnot(None))
        if assembly_no is not None:
            query = query.filter(Ward.assembly_no == assembly_no)
        return query.order_by(Ward.ward_name_en).all()
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
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.get("/api/booths", response_model=List[BoothOut])
def get_booths(ward_id: int | None = None):
    """Get all booths with booth_no, optionally filtered by ward_id"""
    db: Session = SessionLocal()
    try:
        query = db.query(Booth)
        if ward_id:
            query = query.filter(Booth.ward_id == ward_id)
        return query.all()
    finally:
        db.close()


@app.get("/api/booths/{booth_id}", response_model=BoothOut)
def get_booth(booth_id: int):
    """Get a specific booth by id"""
    db: Session = SessionLocal()
    try:
        booth = db.query(Booth).filter(Booth.id == booth_id).first()
        if not booth:
            raise HTTPException(status_code=404, detail="Booth not found")
        return booth
    finally:
        db.close()


@app.post("/api/booths", response_model=BoothOut)
def create_booth(payload: BoothCreate):
    """Create a new booth"""
    db: Session = SessionLocal()
    try:
        booth = Booth(
            ward_id=payload.ward_id,
            booth_no=payload.booth_no,
            booth_add_en=payload.booth_add_en,
            booth_add_local=payload.booth_add_local,
        )
        db.add(booth)
        db.commit()
        db.refresh(booth)
        return booth
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
                options=q.options,
            )
            db.add(new_q)
        
        db.commit()
        return {"message": "Questions updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()
@app.get("/api/voters/search", response_model=List[VoterSearch])
def search_voters(q: str, ward_id: int | None = None):
    """Search voters by name, EPIC, or mobile (1+ characters)."""
    query = (q or "").strip()
    if not query:
        return []

    db: Session = SessionLocal()
    try:
        available = _voter_table_columns(db)
        select_cols = [col for col in _VOTER_SEARCH_FIELDS if col in available]
        if "name_en" not in select_cols:
            select_cols = ["name_en"] + [c for c in select_cols if c != "name_en"]

        search_clauses = []
        if "name_en" in available:
            search_clauses.append("name_en ILIKE :pattern")
        if "epic" in available:
            search_clauses.append("epic ILIKE :pattern")
        if "mobile" in available:
            search_clauses.append("CAST(mobile AS TEXT) ILIKE :pattern")
        if "name_kannada" in available:
            search_clauses.append("name_kannada ILIKE :pattern")
        if not search_clauses:
            return []

        params: dict = {"pattern": f"%{query}%", "limit": 10}
        ward_clause = ""
        if ward_id and "ward_code" in available:
            ward_clause = """
                AND ward_code IN (
                    SELECT ward_code FROM wards WHERE id = :ward_id
                )
            """
            params["ward_id"] = ward_id

        rows = db.execute(
            text(
                f"""
                SELECT {", ".join(select_cols)}
                FROM voters
                WHERE ({' OR '.join(search_clauses)})
                {ward_clause}
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()

        results: list[VoterSearch] = []
        for row in rows:
            payload = {key: row.get(key) for key in select_cols}
            if payload.get("age") is not None:
                payload["age"] = str(payload["age"])
            if payload.get("sl_no") is not None and "sl" not in payload:
                payload["sl"] = str(payload["sl_no"])
            if payload.get("booth") is not None and "booth_no" not in payload:
                payload["booth_no"] = str(payload["booth"])
            results.append(
                VoterSearch(
                    name_en=str(payload.get("name_en") or ""),
                    epic=payload.get("epic"),
                    house=payload.get("house"),
                    name_kannada=payload.get("name_kannada"),
                    gender=payload.get("gender"),
                    age=payload.get("age"),
                    mobile=str(payload["mobile"]) if payload.get("mobile") is not None else None,
                    rel_eng=payload.get("rel_eng"),
                    rel_kannada=payload.get("rel_kannada"),
                    rel_type=payload.get("rel_type"),
                    ward_code=payload.get("ward_code"),
                    address_en=payload.get("address_en"),
                    address_local=payload.get("address_local"),
                    sl=str(payload["sl"]) if payload.get("sl") is not None else None,
                    booth_no=str(payload["booth_no"]) if payload.get("booth_no") is not None else None,
                    caste=payload.get("caste"),
                    religion=payload.get("religion"),
                    education=payload.get("education"),
                )
            )
        return results
    except Exception as exc:
        print(f"[voters/search] failed: {exc}")
        return []
    finally:
        db.close()
