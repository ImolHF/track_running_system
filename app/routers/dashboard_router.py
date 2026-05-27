from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Athlete, Activity
from app.auth import get_current_coach

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db), _=Depends(get_current_coach)):
    athletes = (
        db.query(Athlete).filter(Athlete.is_active == True).order_by(Athlete.name).all()
    )
    return request.app.state.templates.TemplateResponse(request, "dashboard.html", {
        "athletes": athletes,
    })


@router.get("/api/activities/metrics")
async def activity_metrics(
    athlete_id: Optional[int] = Query(None),
    days: int = Query(90, ge=7, le=730),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(Activity).filter(
        Activity.start_time >= cutoff,
        Activity.distance_m > 0,
    )
    if athlete_id is not None:
        q = q.filter(Activity.athlete_id == athlete_id)

    activities = q.order_by(Activity.start_time.asc()).all()

    result = []
    for a in activities:
        result.append({
            "date": a.start_time.strftime("%Y-%m-%d") if a.start_time else "",
            "athlete_name": a.athlete.name if a.athlete else "?",
            "athlete_id": a.athlete_id,
            "activity_id": a.id,
            "name": a.name or a.activity_type,
            "distance_km": round((a.distance_m or 0) / 1000, 2),
            "duration_min": round((a.duration_s or 0) / 60, 1),
            "avg_pace_s_per_km": round(a.avg_pace_s_per_km, 1) if a.avg_pace_s_per_km else None,
            "avg_heart_rate": a.avg_heart_rate,
            "max_heart_rate": a.max_heart_rate,
            "avg_cadence": a.avg_cadence,
            "avg_stride_length_cm": a.avg_stride_length_cm,
            "elevation_gain_m": a.elevation_gain_m,
            "calories": a.calories,
            "avg_temperature_c": a.avg_temperature_c,
            "training_effect_aerobic": a.training_effect_aerobic,
            "training_effect_anaerobic": a.training_effect_anaerobic,
            "vo2max": a.vo2max,
        })
    return JSONResponse(result)


@router.get("/api/dashboard/weekly-totals")
async def weekly_totals(db: Session = Depends(get_db), _=Depends(get_current_coach)):
    cutoff = datetime.utcnow() - timedelta(weeks=12)
    activities = db.query(Activity).filter(Activity.start_time >= cutoff).all()

    weeks = {}
    for a in activities:
        iso = a.start_time.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        if week_key not in weeks:
            weeks[week_key] = {"distance_km": 0, "count": 0}
        weeks[week_key]["distance_km"] += (a.distance_m or 0) / 1000
        weeks[week_key]["count"] += 1

    result = [
        {"week": k, "distance_km": round(v["distance_km"], 1), "count": v["count"]}
        for k, v in sorted(weeks.items())
    ]
    return JSONResponse(result)
