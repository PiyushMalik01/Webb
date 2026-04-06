from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

APP_REGISTRY_PATH = Path(__file__).parent.parent / "app_registry.json"


@router.get("/apps")
def list_apps() -> dict:
    """List known applications."""
    try:
        with open(APP_REGISTRY_PATH, "r") as f:
            registry = json.load(f)
        return {"apps": registry}
    except Exception:
        return {"apps": {}}


@router.post("/apps")
def add_app(payload: dict) -> dict:
    """Add an app to the registry."""
    name = payload.get("name", "").lower().strip()
    path = payload.get("path", "").strip()
    if not name or not path:
        return {"ok": False, "error": "name and path required"}

    try:
        registry = {}
        if APP_REGISTRY_PATH.exists():
            with open(APP_REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        registry[name] = path
        with open(APP_REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
        return {"ok": True, "name": name, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}
