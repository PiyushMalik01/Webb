from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Reminder
from ..schemas import ReminderCreate, ReminderOut

router = APIRouter()


@router.get("/", response_model=list[ReminderOut])
def list_reminders(db: Session = Depends(get_db)) -> list[Reminder]:
    stmt = select(Reminder).order_by(Reminder.created_at.desc())
    return list(db.scalars(stmt).all())


@router.post("/", response_model=ReminderOut)
def create_reminder(payload: ReminderCreate, db: Session = Depends(get_db)) -> Reminder:
    reminder = Reminder(
        message=payload.message,
        trigger_time=payload.trigger_time,
        repeat=payload.repeat,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"ok": True}

