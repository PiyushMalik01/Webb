from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import safety_guard


@dataclass
class Action:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for OpenAI tools format
    fn: Callable[..., str]
    safety: str = "green"  # "green", "yellow", "red"
    category: str = "general"


_registry: Dict[str, Action] = {}


def register(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    fn: Callable[..., str],
    safety: str = "green",
    category: str = "general",
) -> None:
    _registry[name] = Action(
        name=name,
        description=description,
        parameters=parameters,
        fn=fn,
        safety=safety,
        category=category,
    )


def get(name: str) -> Optional[Action]:
    return _registry.get(name)


def execute(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an action with safety checks.
    Returns {"ok": bool, "result": str, "needs_confirmation": bool}
    """
    action = _registry.get(name)
    if action is None:
        return {"ok": False, "result": f"Unknown action: {name}", "needs_confirmation": False}

    # Safety check
    check = safety_guard.check_action(name, params, action.safety)
    if not check.allowed:
        return {"ok": False, "result": check.message, "needs_confirmation": False}
    if check.needs_confirmation:
        return {"ok": False, "result": check.message, "needs_confirmation": True}

    # Execute
    try:
        result = action.fn(**params)
        return {"ok": True, "result": result, "needs_confirmation": False}
    except TypeError as e:
        return {"ok": False, "result": f"Parameter error: {e}", "needs_confirmation": False}
    except Exception as e:
        return {"ok": False, "result": f"Failed: {e}", "needs_confirmation": False}


def list_actions() -> List[Action]:
    return list(_registry.values())


def get_openai_tools() -> List[Dict[str, Any]]:
    """Generate OpenAI tools schema for function calling."""
    tools = []
    for action in _registry.values():
        if action.safety == "red":
            continue  # Don't even tell the AI about red actions
        tools.append({
            "type": "function",
            "function": {
                "name": action.name,
                "description": action.description,
                "parameters": action.parameters,
            }
        })
    return tools


def describe_for_prompt() -> str:
    """Short description for system prompt context."""
    lines = []
    for a in _registry.values():
        if a.safety == "red":
            continue
        confirm = " [needs confirmation]" if a.safety == "yellow" else ""
        lines.append(f"- {a.name}: {a.description}{confirm}")
    return "\n".join(lines)
