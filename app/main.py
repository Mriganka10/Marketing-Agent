import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.google_sync_scheduler import run_google_sync_schedule


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        sync_task = asyncio.create_task(run_google_sync_schedule(settings))
        try:
            yield
        finally:
            sync_task.cancel()
            await asyncio.gather(sync_task, return_exceptions=True)

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(router)
    return app


app = create_app()
