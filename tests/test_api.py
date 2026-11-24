import asyncio
import os
import unittest

os.environ["SESSION_SECRET"] = "test-secret-that-is-long-enough-for-local-tests"

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.main import ChatInput, app, chat_stream, get_db
from api.models import User


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(User.__table__.create)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        async def test_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost:8000"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_register_login_stream_logout(self):
        self.assertEqual((await self.client.get("/auth/me")).status_code, 401)
        self.assertEqual(
            (await self.client.post("/chat/stream", json={"message": "Xin chào"})).status_code,
            401,
        )

        user = {"name": "Bảo", "email": "Bao@Example.com", "password": "safe-password-123"}
        response = await self.client.post("/auth/register", json=user)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "bao@example.com")
        async with self.session_factory() as session:
            saved = await session.get(User, response.json()["id"])
            self.assertTrue(saved.password_hash.startswith("$argon2id$"))
            self.assertNotEqual(saved.password_hash, user["password"])
        self.assertEqual((await self.client.post("/auth/register", json=user)).status_code, 409)
        self.assertEqual(
            (await self.client.post("/auth/login", json={**user, "password": "wrong"})).status_code,
            401,
        )

        response = await self.client.post(
            "/auth/login", json={"email": user["email"], "password": user["password"]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("samesite=strict", response.headers["set-cookie"].lower())
        self.assertEqual((await self.client.get("/auth/me")).json()["name"], "Bảo")

        response = await self.client.post(
            "/chat/stream", json={"message": "Xin chào"},
            headers={"Origin": "http://localhost:5500"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5500")
        self.assertGreater(response.text.count('"type": "text"'), 1)
        self.assertIn('"type": "done"', response.text)

        self.assertEqual((await self.client.post("/auth/logout")).status_code, 200)
        self.assertEqual((await self.client.get("/auth/me")).status_code, 401)

    async def test_validation_and_stream_yields_incrementally(self):
        response = await self.client.post(
            "/auth/register",
            json={"name": "Bảo", "email": "not-an-email", "password": "short"},
        )
        self.assertEqual(response.status_code, 422)

        stream = await chat_stream(ChatInput(message="Kiểm tra"), user=None)
        chunks = stream.body_iterator
        first = await anext(chunks)
        self.assertIn('"type": "text"', first)
        before = asyncio.get_running_loop().time()
        second = await anext(chunks)
        self.assertIn('"type": "text"', second)
        self.assertGreaterEqual(asyncio.get_running_loop().time() - before, 0.04)
        await chunks.aclose()


if __name__ == "__main__":
    unittest.main()
