from datetime import date, datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite는 시간대 정보를 빼고 돌려주므로 UTC로 맞춰준다."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def age_on(birth_date: date, today: date | None = None) -> int:
    """만 나이."""
    today = today or utcnow().date()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years
