from passlib.hash import bcrypt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


async def get_current_coach(request: Request):
    coach_id = request.session.get("coach_id")
    if not coach_id:
        raise HTTPException(status_code=401)
    return coach_id
