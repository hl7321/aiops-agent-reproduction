"""FastAPI persistence lifespan 与 session provider 测试。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite.provider import create_persistence_lifespan, get_session


async def test_lifespan_creates_provider_session_and_closes_runtime(tmp_path: Path) -> None:
    database_path = tmp_path / "provider.sqlite3"
    settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{database_path}")
    app = FastAPI()

    async def session_probe(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, int]:
        value = (await session.execute(text("SELECT 1"))).scalar_one()
        return {"value": value}

    app.add_api_route("/session", session_probe, methods=["GET"])

    lifespan = create_persistence_lifespan(settings)
    async with lifespan(app):
        runtime = app.state.persistence_runtime
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/session")
            assert response.json() == {"value": 1}
            assert database_path.exists()

    assert not hasattr(app.state, "persistence_runtime")
    try:
        _ = runtime.session_factory
    except RuntimeError as error:
        assert "已关闭" in str(error)
    else:
        raise AssertionError("lifespan 退出后 runtime 仍可提供 session factory")
