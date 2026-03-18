from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Priority = Literal["low", "medium", "high"]
Repeat = Literal["none", "daily", "weekly"]
Face = Literal["IDLE", "HAPPY", "FOCUS", "SLEEPY", "REMINDER", "LISTENING", "SURPRISED"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    priority: Priority = "medium"
    due_date: Optional[str] = None  # ISO date string


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    priority: Optional[Priority] = None
    due_date: Optional[str] = None
    completed: Optional[bool] = None


class TaskOut(BaseModel):
    id: int
    title: str
    priority: str
    due_date: Optional[str]
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderCreate(BaseModel):
    message: str = Field(min_length=1)
    trigger_time: str  # ISO datetime string
    repeat: Repeat = "none"


class ReminderOut(BaseModel):
    id: int
    message: str
    trigger_time: str
    repeat: str
    triggered: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TimerStart(BaseModel):
    duration_minutes: int = Field(ge=1, le=240)


class TimerStatus(BaseModel):
    state: Literal["idle", "running", "paused"]
    seconds_remaining: int
    duration_seconds: int


class FaceSet(BaseModel):
    face: Face


class WebbStatus(BaseModel):
    connected: bool
    port: Optional[str]
    baud: int
    last_face: Optional[str]
    last_error: Optional[str]

