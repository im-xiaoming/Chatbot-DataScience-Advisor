from __future__ import annotations

import asyncio
import json
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from api.database import session_factory
from api.models import User


load_dotenv()
session_secret = os.getenv("SESSION_SECRET")
if not session_secret:
    raise RuntimeError("Set SESSION_SECRET in .env before starting the API.")

app = FastAPI(title="DataPath API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5500")],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="datapath_session",
    same_site="strict",
    https_only=os.getenv("COOKIE_SECURE") == "true",
    max_age=60 * 60 * 8,
)
password_hasher = PasswordHasher()


class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


async def get_db():
    async with session_factory()() as session:
        yield session


async def current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    user = await db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


@app.post("/auth/register", response_model=UserOutput, status_code=201)
async def register(data: RegisterInput, db: AsyncSession = Depends(get_db)):
    user = User(
        name=data.name.strip(),
        email=str(data.email).lower(),
        password_hash=password_hasher.hash(data.password),
    )
    if not user.name:
        raise HTTPException(status_code=422, detail="Name is required.")
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered.") from None
    await db.refresh(user)
    return user


@app.post("/auth/login", response_model=UserOutput)
async def login(data: LoginInput, request: Request, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == str(data.email).lower()))
    try:
        valid = bool(user) and password_hasher.verify(user.password_hash, data.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    request.session["user_id"] = user.id
    return user


@app.get("/auth/me", response_model=UserOutput)
async def me(user: User = Depends(current_user)):
    return user


@app.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(data: ChatInput, user: User = Depends(current_user)):
    async def events():
        reply = (
            f"Đây là câu trả lời mô phỏng cho câu hỏi: {data.message.strip()}\n\n"
            "API đang gửi nội dung dần từ máy chủ. "
            "Khi RAG và LLM sẵn sàng, phần này sẽ được thay bằng câu trả lời dựa trên tài liệu."
        )
        for word in reply.split(" "):
            yield sse({"type": "text", "content": word + " "})
            await asyncio.sleep(0.06)
        yield sse({"type": "done"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
