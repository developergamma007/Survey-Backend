import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Union

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days — cleared on manual logout client-side

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

SUBMIT_BLOCKED_USERNAMES = frozenset({"admin", "admin@iswot.io"})
RESPONSES_ADMIN_USERNAME = "admin@iswot.io"


def is_responses_admin(username: str | None) -> bool:
    if not username:
        return False
    return username.strip().lower() == RESPONSES_ADMIN_USERNAME


def is_listable_surveyor_user(
    username: str | None,
    display_name: str | None = None,
    mobile: str | None = None,
) -> bool:
    """Survey users shown in admin Users tab (excludes admin accounts)."""
    if is_blocked_surveyor_identity(display_name, mobile, username):
        return False
    if not username:
        return False
    normalized = username.strip().lower()
    if normalized in {"admin", RESPONSES_ADMIN_USERNAME}:
        return False
    if normalized.startswith("admin@iswot"):
        return False
    if "admin_iswot" in normalized or normalized.startswith("surveyor_admin"):
        return False
    return True


def is_blocked_surveyor_identity(
    display_name: str | None,
    mobile: str | None = None,
    username: str | None = None,
) -> bool:
    """Block admin identities from surveyor sign-in and users list."""
    name = normalize_name(display_name or "")
    if name in {"admin", RESPONSES_ADMIN_USERNAME} or name.startswith("admin@iswot"):
        return True

    un = (username or "").strip().lower()
    if un in {"admin", RESPONSES_ADMIN_USERNAME} or un.startswith("admin@iswot"):
        return True
    if "admin_iswot" in un or un.startswith("surveyor_admin"):
        return True

    return False


def is_submit_blocked_username(username: str | None) -> bool:
    if not username:
        return False
    normalized = username.strip().lower()
    return normalized in SUBMIT_BLOCKED_USERNAMES or normalized.startswith("admin@iswot")

auth_engine = create_engine(DATABASE_URL, echo=False, future=True)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)
AuthBase = declarative_base()


class SurveyUser(AuthBase):
    __tablename__ = "survey_users"
    __table_args__ = {"schema": "survey"}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    display_name = Column(String(255), nullable=True)
    mobile = Column(String(32), nullable=True)
    disabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: str
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str


class UserProfile(BaseModel):
    username: str
    display_name: str
    mobile: str
    is_admin: bool


def resolve_display_name(username: str, display_name: str | None = None) -> str:
    if display_name and str(display_name).strip():
        return normalize_name(display_name)
    if "@" in username:
        local = username.split("@", 1)[0].strip()
        if local:
            return normalize_name(local)
    return normalize_name(username)


def resolve_mobile(mobile: str | None = None) -> str:
    return str(mobile or "").strip()


def normalize_mobile(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def is_admin_username(username: str | None) -> bool:
    return is_responses_admin(username)


def build_user_profile(username: str, display_name: str | None = None, mobile: str | None = None) -> UserProfile:
    return UserProfile(
        username=username,
        display_name=resolve_display_name(username, display_name),
        mobile=resolve_mobile(mobile),
        is_admin=is_admin_username(username),
    )

# Mock User Database
# admin / admin  |  admin@iswot.io / 8867038709 (field admin)
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$y5THdVd56K2gvIRMlwC5sOK.Am.HGbthUp0L1aPWnzcIP7c6HLT6u",
        "disabled": False,
    },
    "admin@iswot.io": {
        "username": "admin@iswot.io",
        "hashed_password": "$2b$12$MX9SY/SK5YbA70fZXEy40O0HZaq6iYroJ7jakYWKlmSOi8dnifYPu",
        "disabled": False,
    },
}


def get_survey_user_row(username: str) -> SurveyUser | None:
    db = AuthSessionLocal()
    try:
        return db.query(SurveyUser).filter(SurveyUser.username == username).first()
    except Exception as e:
        print(f"[auth] survey_users lookup failed: {e}")
        return None
    finally:
        db.close()


def get_user_from_db(username: str):
    row = get_survey_user_row(username)
    if not row:
        return None
    return UserInDB(
        username=row.username,
        hashed_password=row.hashed_password,
        disabled=row.disabled,
    )


def get_user_profile(username: str) -> UserProfile | None:
    row = get_survey_user_row(username)
    if row:
        return build_user_profile(row.username, row.display_name, row.mobile)
    if username in fake_users_db:
        return build_user_profile(username)
    return None


def get_user(db, username: str):
    user = get_user_from_db(username)
    if user:
        return user
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None


def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def _user_in_db_from_row(row: SurveyUser) -> UserInDB:
    return UserInDB(
        username=row.username,
        hashed_password=row.hashed_password,
        disabled=row.disabled,
    )


def _surveyor_username(name_key: str, mobile_key: str) -> str:
    safe_name = re.sub(r"[^a-z0-9]+", "_", name_key).strip("_") or "surveyor"
    return f"surveyor_{safe_name}_{mobile_key}"


def get_or_create_surveyor(display_name: str, mobile: str) -> UserInDB | None:
    """Find surveyor by lowercase name + mobile, or create once on first sign-in."""
    name_key = normalize_name(display_name)
    mobile_key = normalize_mobile(mobile)
    if not name_key or len(mobile_key) < 10:
        return None
    if is_blocked_surveyor_identity(display_name, mobile):
        return None

    db = AuthSessionLocal()
    try:
        rows = db.query(SurveyUser).filter(SurveyUser.disabled == False).all()
        for row in rows:
            if is_responses_admin(row.username) or row.username == "admin":
                continue
            row_name = normalize_name(row.display_name or "")
            row_mobile = normalize_mobile(row.mobile or "")
            if row_name == name_key and row_mobile == mobile_key:
                return _user_in_db_from_row(row)

        username = _surveyor_username(name_key, mobile_key)
        if db.query(SurveyUser).filter(SurveyUser.username == username).first():
            username = f"{username}_{secrets.token_hex(3)}"

        hashed = bcrypt.hashpw(mobile_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        row = SurveyUser(
            username=username,
            hashed_password=hashed,
            display_name=name_key,
            mobile=mobile_key,
            disabled=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _user_in_db_from_row(row)
    except Exception as e:
        db.rollback()
        print(f"[auth] get_or_create_surveyor failed: {e}")
        return None
    finally:
        db.close()


def authenticate_surveyor(display_name: str, mobile: str) -> UserInDB | None:
    return get_or_create_surveyor(display_name, mobile)

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_optional_user(token: str | None = Depends(oauth2_scheme_optional)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = get_user(fake_users_db, username=username)
        if user is None or user.disabled:
            return None
        return user
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None or user.disabled:
        raise credentials_exception
    return user


async def require_responses_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_responses_admin(current_user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Responses are only available to the admin account.",
        )
    return current_user
