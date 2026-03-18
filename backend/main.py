from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routes.reminders import router as reminders_router
from .routes.tasks import router as tasks_router
from .routes.timer import router as timer_router
from .routes.webb import router as webb_router
from .routes.voice import router as voice_router
from .routes.notifications import router as notifications_router
from .idle_manager import idle_manager


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(title="Webb Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        Base.metadata.create_all(bind=engine)
        idle_manager.start()

    app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(reminders_router, prefix="/api/reminders", tags=["reminders"])
    app.include_router(timer_router, prefix="/api/timer", tags=["timer"])
    app.include_router(webb_router, prefix="/api/webb", tags=["webb"])
    app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
    app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": os.getenv("ENV", "dev")}

    return app


app = create_app()

