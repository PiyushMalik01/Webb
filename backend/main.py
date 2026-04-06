from __future__ import annotations

import asyncio
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
from .notifications_hub import hub
from .reminder_scheduler import reminder_check_loop
from .routes.timer import shutdown_timer_background
from .serial_manager import get_serial_manager
from .voice_engine import start as start_voice, stop as stop_voice
from . import activity_monitor, system_controller, ai_manager, streaming_tts
from .routes.activity import router as activity_router
from .routes.system import router as system_router


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
    async def _startup() -> None:
        Base.metadata.create_all(bind=engine)
        hub.bind_loop(asyncio.get_running_loop())

        if not os.getenv("OPENAI_API_KEY"):
            print("[webb] warning: OPENAI_API_KEY is not set; voice and AI nudges will fall back.")

        idle_manager.start()
        app.state.reminder_task = asyncio.create_task(reminder_check_loop())

        system_controller.register_all_actions()
        ai_manager.register_task_actions()
        activity_monitor.start()
        start_voice()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        reminder_task = getattr(app.state, "reminder_task", None)
        if reminder_task is not None:
            reminder_task.cancel()
            try:
                await reminder_task
            except asyncio.CancelledError:
                pass
        stop_voice()
        activity_monitor.stop()
        streaming_tts.shutdown()
        idle_manager.stop()
        await shutdown_timer_background()
        get_serial_manager().close()

    app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(reminders_router, prefix="/api/reminders", tags=["reminders"])
    app.include_router(timer_router, prefix="/api/timer", tags=["timer"])
    app.include_router(webb_router, prefix="/api/webb", tags=["webb"])
    app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
    app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
    app.include_router(activity_router, prefix="/api/activity", tags=["activity"])
    app.include_router(system_router, prefix="/api/system", tags=["system"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": os.getenv("ENV", "dev")}

    return app


app = create_app()

