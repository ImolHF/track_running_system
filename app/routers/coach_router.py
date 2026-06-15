from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Athlete, Activity, TrainingPlan, CoachMessage
from app.auth import get_current_coach
from app.ai_client import chat, build_athlete_context

router = APIRouter()


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


@router.get("/api/coach/messages")
async def get_messages(
    athlete_id: int = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    messages = (
        db.query(CoachMessage)
        .filter(CoachMessage.athlete_id == athlete_id)
        .order_by(CoachMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return JSONResponse([{
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.strftime("%m-%d %H:%M") if m.created_at else "",
    } for m in messages])


@router.post("/api/coach/chat")
async def coach_chat(
    request: Request,
    athlete_id: int = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return JSONResponse({"error": "运动员不存在"}, status_code=404)

    # Save user message
    user_msg = CoachMessage(athlete_id=athlete_id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    # Gather training data as context
    cutoff = datetime.utcnow() - timedelta(days=90)
    activities = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.start_time >= cutoff)
        .order_by(Activity.start_time.desc())
        .limit(50)
        .all()
    )
    context = build_athlete_context(athlete.name, activities)

    # Build conversation history
    history = (
        db.query(CoachMessage)
        .filter(CoachMessage.athlete_id == athlete_id)
        .order_by(CoachMessage.created_at.desc())
        .limit(20)
        .all()
    )
    history.reverse()

    messages = [{"role": m.role, "content": m.content} for m in history]
    messages[-1]["content"] = f"运动员训练数据：\n\n{context}\n\n用户消息：{message}"

    # Get AI reply
    reply = await chat(messages)

    # Save AI reply
    ai_msg = CoachMessage(athlete_id=athlete_id, role="assistant", content=reply)
    db.add(ai_msg)
    db.commit()

    return JSONResponse({
        "reply": reply,
        "created_at": ai_msg.created_at.strftime("%m-%d %H:%M"),
    })


@router.post("/api/coach/create-plan")
async def create_training_plan(
    request: Request,
    athlete_id: int = Form(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_coach),
):
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return JSONResponse({"error": "运动员不存在"}, status_code=404)

    # Gather training data
    cutoff = datetime.utcnow() - timedelta(days=90)
    activities = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.start_time >= cutoff)
        .order_by(Activity.start_time.desc())
        .limit(50)
        .all()
    )
    context = build_athlete_context(athlete.name, activities)

    prompt = f"""请根据以下运动员的训练数据，制定一个为期4周的科学训练计划。

{context}

要求：
1. 用Markdown表格呈现训练计划，包含日期、训练内容、配速区间、心率区间、训练时长
2. 每周要有不同的训练重点（如有氧基础、乳酸阈值、速度耐力等）
3. 合理安排强度课和恢复课的比例（建议每周2-3次强度课）
4. 在计划末尾给出训练目标和建议
"""

    reply = await chat([
        {"role": "user", "content": prompt}
    ])

    # Save plan
    existing = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id)
        .order_by(TrainingPlan.created_at.desc())
        .first()
    )
    plan = TrainingPlan(athlete_id=athlete_id, content=reply)
    db.add(plan)
    db.commit()

    # Save as chat messages
    db.add(CoachMessage(athlete_id=athlete_id, role="user", content="请为我制定训练计划"))
    db.add(CoachMessage(athlete_id=athlete_id, role="assistant", content=reply))
    db.commit()

    return JSONResponse({"reply": reply})
