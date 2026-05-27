from cryptography.fernet import Fernet
from app.config import FERNET_KEY

_fernet = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None


def encrypt_garmin_password(password: str) -> str:
    return _fernet.encrypt(password.encode()).decode()


def decrypt_garmin_password(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


def format_pace(seconds_per_km: float | None) -> str:
    if seconds_per_km is None or seconds_per_km <= 0:
        return "--"
    minutes = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{minutes}'{secs:02d}\""


def format_duration(total_seconds: float | None) -> str:
    if total_seconds is None or total_seconds <= 0:
        return "--"
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_distance(meters: float | None) -> str:
    if meters is None or meters <= 0:
        return "--"
    km = meters / 1000
    return f"{km:.2f} km"
