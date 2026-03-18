from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task
from ..schemas import TaskCreate, TaskOut, TaskUpdate
from ..serial_manager import get_serial_manager

router = APIRouter()


@router.get("/", response_model=list[TaskOut])
def list_tasks(
    completed: Optional[bool] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc())
    if completed is not None:
        stmt = stmt.where(Task.completed == completed)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    return list(db.scalars(stmt).all())


@router.post("/", response_model=TaskOut)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    task = Task(title=payload.title, priority=payload.priority, due_date=payload.due_date)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.completed = True
    db.commit()
    db.refresh(task)

    try:
        get_serial_manager().send_face("HAPPY")
    except Exception:
        pass

    return task

