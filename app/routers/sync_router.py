import asyncio
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models import Athlete, SyncLog
from app.auth import get_current_coach, hash_password, verify_password
from app.sync_engine import sync_athlete, sync_all_athletes

router = APIRouter()


def _sync_all_in_background(sync_type: str):
    db = SessionLocal()
    try:
        sync_all_athletes(db, sync_type)
    finally:
        db.close()


def _sync_one_in_background(athlete_id: int, sync_type: str):
    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete:
            sync_athlete(athlete, db, sync_type)
    finally:
        db.close()


@router.post("/sync")
async def sync_all(request: Request, _=Depends(get_current_coach)):
    asyncio.create_task(asyncio.to_thread(_sync_all_in_background, "manual"))
    request.session["flash_message"] = "info"
    request.session["flash_text"] = "同步任务已开始，请稍后查看同步日志"
    return RedirectResponse("/sync/logs", status_code=303)


@router.post("/sync/{athlete_id}")
async def sync_one(
    request: Request, athlete_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        request.session["flash_message"] = "error"
        request.session["flash_text"] = "运动员不存在"
        return RedirectResponse("/athletes", status_code=303)

    asyncio.create_task(asyncio.to_thread(_sync_one_in_background, athlete_id, "manual"))
    request.session["flash_message"] = "info"
    request.session["flash_text"] = f"{athlete.name} 的同步任务已开始，请稍后刷新查看"
    return RedirectResponse(f"/athletes/{athlete_id}", status_code=303)


@router.get("/sync/logs")
async def sync_logs(
    request: Request, page: int = Query(1, ge=1),
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    per_page = 30
    total = db.query(SyncLog).count()
    logs = (
        db.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    return request.app.state.templates.TemplateResponse(request, "sync_logs.html", {
        "logs": logs,
        "page": page,
        "total_pages": total_pages,
    })


@router.get("/settings")
async def settings_page(request: Request, _=Depends(get_current_coach)):
    return request.app.state.templates.TemplateResponse(request, "settings.html")


@router.post("/settings")
async def save_settings(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    from app.models import Coach
    coach_id = request.session.get("coach_id")
    coach = db.query(Coach).filter(Coach.id == coach_id).first()

    if not verify_password(old_password, coach.password_hash):
        request.session["flash_message"] = "error"
        request.session["flash_text"] = "原密码错误"
        return RedirectResponse("/settings", status_code=303)

    if new_password != new_password2:
        request.session["flash_message"] = "error"
        request.session["flash_text"] = "两次输入的新密码不一致"
        return RedirectResponse("/settings", status_code=303)

    if len(new_password) < 4:
        request.session["flash_message"] = "error"
        request.session["flash_text"] = "密码长度至少4位"
        return RedirectResponse("/settings", status_code=303)

    coach.password_hash = hash_password(new_password)
    db.commit()
    request.session["flash_message"] = "success"
    request.session["flash_text"] = "密码已修改"
    return RedirectResponse("/settings", status_code=303)
