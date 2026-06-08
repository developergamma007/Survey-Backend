import os
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
ACCESS_TOKEN_EXPIRE_MINUTES = 720  # 12 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

auth_engine = create_engine(DATABASE_URL, echo=False, future=True)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)
AuthBase = declarative_base()


class SurveyUser(AuthBase):
    __tablename__ = "survey_users"
    __table_args__ = {"schema": "survey"}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
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


def get_user_from_db(username: str):
    db = AuthSessionLocal()
    try:
        row = db.query(SurveyUser).filter(SurveyUser.username == username).first()
        if not row:
            return None
        return UserInDB(
            username=row.username,
            hashed_password=row.hashed_password,
            disabled=row.disabled,
        )
    finally:
        db.close()


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

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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
