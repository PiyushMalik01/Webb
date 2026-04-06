from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Action:
    name: str
    description: str
    params: List[str]
    fn: Callable[..., str]
    category: str = "general"


_registry: Dict[str, Action] = {}


def register(
    name: str,
    description: str,
    params: List[str],
    fn: Callable[..., str],
    category: str = "general",
) -> None:
    """Register an action that the AI can invoke."""
    _registry[name] = Action(
        name=name,
        description=description,
        params=params,
        fn=fn,
        category=category,
    )


def get(name: str) -> Optional[Action]:
    """Look up an action by name."""
    return _registry.get(name)


def execute(name: str, params: Dict[str, Any]) -> str:
    """Execute a registered action with the given parameters. Returns a result string."""
    action = _registry.get(name)
    if action is None:
        return f"Unknown action: {name}"
    try:
        return action.fn(**params)
    except TypeError as e:
        return f"Action {name} parameter error: {e}"
    except Exception as e:
        return f"Action {name} failed: {e}"


def list_actions() -> List[Action]:
    """Return all registered actions."""
    return list(_registry.values())


def describe_for_ai() -> str:
    """Generate a description of all actions for the AI system prompt."""
    lines = []
    for action in _registry.values():
        param_str = ", ".join(action.params) if action.params else "(no params)"
        lines.append(f"- {action.name}({param_str}): {action.description}")
    return "\n".join(lines)
