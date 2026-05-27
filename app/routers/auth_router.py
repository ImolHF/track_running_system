from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Coach
from app.auth import verify_password, hash_password, get_current_coach

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = next(get_db())
    coach = db.query(Coach).filter(Coach.username == username).first()

    if not coach:
        coach = db.query(Coach).first()
        if not coach:
            coach = Coach(username=username, password_hash=hash_password(password), display_name=username)
            db.add(coach)
            db.commit()
            db.refresh(coach)
            request.session["coach_id"] = coach.id
            request.session["flash_message"] = "success"
            request.session["flash_text"] = f"教练账号已创建，欢迎 {username}！"
            return RedirectResponse("/", status_code=303)

    if not verify_password(password, coach.password_hash):
        request.session["flash_message"] = "error"
        request.session["flash_text"] = "密码错误"
        return RedirectResponse("/login", status_code=303)

    request.session["coach_id"] = coach.id
    request.session["flash_message"] = "success"
    request.session["flash_text"] = "登录成功"
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
