from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


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


def kst_day_start(now: datetime | None = None) -> datetime:
    """오늘(한국 시간) 0시를 UTC로 돌려준다. 하루 LIKE 개수를 셀 때 쓴다."""
    now_kst = (now or utcnow()).astimezone(KST)
    return now_kst.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
