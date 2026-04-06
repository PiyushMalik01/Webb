from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


# Safety tiers
GREEN = "green"    # Execute immediately
YELLOW = "yellow"  # Confirm with user first
RED = "red"        # Always refuse


@dataclass
class SafetyResult:
    allowed: bool
    needs_confirmation: bool
    message: str


# Paths that should NEVER be accessed/modified
BLOCKED_PATHS = [
    "windows\\system32", "windows\\syswow64",
    "program files", "program files (x86)", "programdata",
    "boot.ini", "bootmgr", "ntldr",
    ".ssh", ".gnupg", ".aws",
    ".env", "credentials", "secrets", "tokens",
    "appdata\\local\\microsoft\\credentials",
    "system volume information",
    "$recycle.bin",
]

# File extensions that should never be deleted
BLOCKED_EXTENSIONS = [
    ".sys", ".dll", ".exe", ".msi",
    ".reg", ".bat", ".cmd", ".ps1", ".vbs",
]

# Commands that should never be run
BLOCKED_COMMANDS = [
    "format", "del /s", "rmdir /s", "rd /s",
    "reg delete", "reg add",
    "bcdedit", "diskpart",
    "net user", "net localgroup",
    "netsh advfirewall", "netsh firewall",
    "sc delete", "sc stop",
    "powershell -enc", "powershell -encodedcommand",
    "shutdown /s", "shutdown /r",  # These go through YELLOW instead
]


def check_action(action_name: str, params: dict, safety_tier: str) -> SafetyResult:
    """Validate an action against safety rules."""

    # RED actions are always blocked
    if safety_tier == RED:
        return SafetyResult(
            allowed=False,
            needs_confirmation=False,
            message=f"I can't do that — it could damage your system.",
        )

    # Check file path safety for file operations
    if action_name in ("delete_file", "move_file", "open_file", "run_command"):
        path = params.get("path", "") or params.get("src", "") or params.get("cmd", "")
        path_check = validate_path(path)
        if not path_check.allowed:
            return path_check

    # Check command safety
    if action_name == "run_command":
        cmd = params.get("cmd", "")
        cmd_check = validate_command(cmd)
        if not cmd_check.allowed:
            return cmd_check

    # YELLOW actions need confirmation
    if safety_tier == YELLOW:
        return SafetyResult(
            allowed=True,
            needs_confirmation=True,
            message=f"This needs your confirmation.",
        )

    # GREEN — go ahead
    return SafetyResult(
        allowed=True,
        needs_confirmation=False,
        message="",
    )


def validate_path(path: str) -> SafetyResult:
    """Check if a file path is safe to operate on."""
    if not path:
        return SafetyResult(allowed=True, needs_confirmation=False, message="")

    path_lower = path.lower().replace("/", "\\")

    for blocked in BLOCKED_PATHS:
        if blocked in path_lower:
            return SafetyResult(
                allowed=False,
                needs_confirmation=False,
                message=f"I can't access system-protected paths.",
            )

    return SafetyResult(allowed=True, needs_confirmation=False, message="")


def validate_command(cmd: str) -> SafetyResult:
    """Check if a shell command is safe to run."""
    if not cmd:
        return SafetyResult(allowed=True, needs_confirmation=False, message="")

    cmd_lower = cmd.lower().strip()

    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return SafetyResult(
                allowed=False,
                needs_confirmation=False,
                message=f"I can't run that command — it could damage your system.",
            )

    return SafetyResult(allowed=True, needs_confirmation=True, message="Let me confirm before running this.")
