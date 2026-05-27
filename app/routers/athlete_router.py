from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Athlete, Activity
from app.auth import get_current_coach
from app.utils import encrypt_garmin_password

router = APIRouter()


@router.get("/athletes")
async def athlete_list(request: Request, db: Session = Depends(get_db), _=Depends(get_current_coach)):
    athletes = db.query(Athlete).order_by(Athlete.name).all()
    return request.app.state.templates.TemplateResponse(request, "athletes.html", {
        "athletes": athletes,
    })


@router.get("/athletes/new")
async def new_athlete_form(request: Request, _=Depends(get_current_coach)):
    return request.app.state.templates.TemplateResponse(request, "athlete_form.html", {
        "athlete": None,
    })


@router.post("/athletes/new")
async def create_athlete(
    request: Request,
    name: str = Form(...),
    garmin_email: str = Form(...),
    garmin_password: str = Form(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    existing = db.query(Athlete).filter(Athlete.garmin_email == garmin_email).first()
    if existing:
        request.session["flash_message"] = "error"
        request.session["flash_text"] = f"佳明账号 {garmin_email} 已存在"
        return RedirectResponse("/athletes/new", status_code=303)

    athlete = Athlete(
        name=name,
        garmin_email=garmin_email,
        garmin_password_encrypted=encrypt_garmin_password(garmin_password),
    )
    db.add(athlete)
    db.commit()
    request.session["flash_message"] = "success"
    request.session["flash_text"] = f"运动员 {name} 已添加"
    return RedirectResponse("/athletes", status_code=303)


@router.get("/athletes/{athlete_id}")
async def athlete_detail(
    request: Request,
    athlete_id: int,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/athletes", status_code=303)

    per_page = 20
    total = db.query(Activity).filter(Activity.athlete_id == athlete_id).count()
    activities = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_time.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    return request.app.state.templates.TemplateResponse(request, "athlete_detail.html", {
        "athlete": athlete,
        "activities": activities,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/athletes/{athlete_id}/edit")
async def edit_athlete_form(
    request: Request, athlete_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/athletes", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "athlete_form.html", {
        "athlete": athlete,
    })


@router.post("/athletes/{athlete_id}/edit")
async def update_athlete(
    request: Request, athlete_id: int,
    name: str = Form(...),
    garmin_email: str = Form(...),
    garmin_password: str = Form(""),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/athletes", status_code=303)

    athlete.name = name
    athlete.garmin_email = garmin_email
    athlete.is_active = is_active
    if garmin_password:
        athlete.garmin_password_encrypted = encrypt_garmin_password(garmin_password)
    db.commit()
    request.session["flash_message"] = "success"
    request.session["flash_text"] = f"运动员 {name} 已更新"
    return RedirectResponse(f"/athletes/{athlete_id}", status_code=303)


@router.get("/athletes/{athlete_id}/delete")
async def delete_athlete_form(
    request: Request, athlete_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/athletes", status_code=303)
    activity_count = db.query(Activity).filter(Activity.athlete_id == athlete_id).count()
    return request.app.state.templates.TemplateResponse(request, "athlete_delete.html", {
        "athlete": athlete,
        "activity_count": activity_count,
    })


@router.post("/athletes/{athlete_id}/delete")
async def delete_athlete(
    request: Request, athlete_id: int,
    db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/athletes", status_code=303)
    name = athlete.name
    db.delete(athlete)
    db.commit()
    request.session["flash_message"] = "success"
    request.session["flash_text"] = f"运动员 {name} 及其所有数据已删除"
    return RedirectResponse("/athletes", status_code=303)


@router.get("/api/athletes/{athlete_id}/weekly-distance")
async def weekly_distance(
    athlete_id: int, db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    cutoff = datetime.utcnow() - timedelta(weeks=12)
    activities = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.start_time >= cutoff)
        .all()
    )
    weeks = {}
    for a in activities:
        iso = a.start_time.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        weeks[week_key] = weeks.get(week_key, 0) + (a.distance_m or 0) / 1000

    result = [{"week": k, "distance_km": round(v, 2)} for k, v in sorted(weeks.items())]
    return JSONResponse(result)


@router.get("/api/athletes/{athlete_id}/pace-trend")
async def pace_trend(
    athlete_id: int, db: Session = Depends(get_db), _=Depends(get_current_coach),
):
    cutoff = datetime.utcnow() - timedelta(weeks=12)
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.avg_pace_s_per_km.isnot(None),
        )
        .order_by(Activity.start_time.asc())
        .all()
    )
    result = [{
        "date": a.start_time.strftime("%Y-%m-%d"),
        "pace": round(a.avg_pace_s_per_km, 1),
    } for a in activities]
    return JSONResponse(result)
