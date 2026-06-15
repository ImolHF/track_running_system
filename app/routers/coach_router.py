from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Athlete, Activity, Lap, TrainingPlan, CoachMessage
from app.auth import get_current_coach
from app.ai_client import chat, build_athlete_context

router = APIRouter()


def _load_laps(db: Session, activities: list) -> dict:
    if not activities:
        return {}
    activity_ids = [a.id for a in activities]
    all_laps = (
        db.query(Lap)
        .filter(Lap.activity_id.in_(activity_ids))
        .order_by(Lap.activity_id, Lap.lap_number)
        .all()
    )
    laps_map = {}
    for lap in all_laps:
        laps_map.setdefault(lap.activity_id, []).append(lap)
    return laps_map


def _get_activities(db: Session, athlete_id: int):
    cutoff = datetime.utcnow() - timedelta(days=90)
    return (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.start_time >= cutoff)
        .order_by(Activity.start_time.desc())
        .limit(30)
        .all()
    )


@router.get("/")
async def coach_home(
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athletes = db.query(Athlete).filter(Athlete.is_active == True).order_by(Athlete.name).all()
    return request.app.state.templates.TemplateResponse(request, "coach.html", {
        "athletes": athletes,
    })


@router.get("/api/coach/plans")
async def get_plans(
    athlete_id: int = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    plans = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id)
        .order_by(TrainingPlan.created_at.desc())
        .limit(20)
        .all()
    )
    return JSONResponse([{
        "id": p.id,
        "name": p.name,
        "created_at": p.created_at.strftime("%m-%d %H:%M"),
    } for p in plans])


@router.get("/api/coach/plan/{plan_id}")
async def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    if not plan:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({
        "id": plan.id,
        "name": plan.name,
        "content": plan.content,
        "athlete_id": plan.athlete_id,
    })


@router.get("/api/coach/messages")
async def get_messages(
    plan_id: int = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    messages = (
        db.query(CoachMessage)
        .filter(CoachMessage.plan_id == plan_id)
        .order_by(CoachMessage.created_at.asc())
        .all()
    )
    return JSONResponse([{
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.strftime("%m-%d %H:%M") if m.created_at else "",
    } for m in messages])


@router.post("/api/coach/create-plan")
async def create_training_plan(
    request: Request,
    athlete_id: int = Form(...),
    user_info: str = Form(""),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return JSONResponse({"error": "运动员不存在"}, status_code=404)

    activities = _get_activities(db, athlete_id)
    laps_map = _load_laps(db, activities)
    context = build_athlete_context(athlete.name, activities, laps_map)

    now_str = datetime.utcnow().strftime("%m月%d日")
    prompt = f"""请根据以下运动员的训练数据和用户需求，制定一个为期4周的科学训练计划。

用户需求：
{user_info}

近期训练数据：
{context}

要求：
1. 计划名称格式：「{athlete.name} 四周训练计划（{now_str}起）」
2. 用Markdown表格呈现，包含日期、训练内容、配速区间、心率区间、训练时长
3. 每周要有不同的训练重点
4. 根据用户需求定制训练强度和内容
5. 合理安排强度课和恢复课的比例
6. 在计划末尾给出训练目标和建议
"""

    reply = await chat([{"role": "user", "content": prompt}])

    plan = TrainingPlan(
        athlete_id=athlete_id,
        name=f"{athlete.name} 四周训练计划（{now_str}起）",
        content=reply,
    )
    db.add(plan)
    db.commit()

    db.add(CoachMessage(athlete_id=athlete_id, plan_id=plan.id, role="user", content="请为我制定训练计划"))
    db.add(CoachMessage(athlete_id=athlete_id, plan_id=plan.id, role="assistant", content=reply))
    db.commit()

    return JSONResponse({
        "plan_id": plan.id,
        "name": plan.name,
        "content": reply,
    })


@router.post("/api/coach/chat")
async def coach_chat(
    request: Request,
    plan_id: int = Form(...),
    athlete_id: int = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    if not plan:
        return JSONResponse({"error": "计划不存在"}, status_code=404)

    # Save user message
    user_msg = CoachMessage(athlete_id=athlete_id, plan_id=plan_id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    # Gather training data
    activities = _get_activities(db, athlete_id)
    laps_map = _load_laps(db, activities)
    context = build_athlete_context(plan.name, activities, laps_map)

    # Build conversation history for this plan
    history = (
        db.query(CoachMessage)
        .filter(CoachMessage.plan_id == plan_id)
        .order_by(CoachMessage.created_at.desc())
        .limit(20)
        .all()
    )
    history.reverse()

    messages = [{"role": m.role, "content": m.content} for m in history]
    messages[-1]["content"] = (
        f"当前训练计划：\n{plan.content[:2000]}\n\n"
        f"最新训练数据：\n{context}\n\n"
        f"用户消息：{message}"
    )

    reply = await chat(messages)

    ai_msg = CoachMessage(athlete_id=athlete_id, plan_id=plan_id, role="assistant", content=reply)
    db.add(ai_msg)
    db.commit()

    return JSONResponse({
        "reply": reply,
        "created_at": ai_msg.created_at.strftime("%m-%d %H:%M"),
    })
