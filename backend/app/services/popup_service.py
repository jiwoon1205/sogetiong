"""공지 팝업 켜기/끄기 (2026-11-24). 관리자 → 공지 팝업 화면에서 바꾼다.

- "invite": 친구 10명 초대 → 평생 VIP 이벤트 팝업 (매일 한 번, 가입한 날은 빼고)
- "install": 앱 설치 안내 팝업 (3일에 한 번, 다른 팝업이 없을 때만)
값은 app_settings 표에 "popup_enabled:<이름>" = "true"/"false". 값이 없으면 켜진 것.
찬반 투표(설문)는 따로 관리자 → 설문에서 켜고 끈다.
"""

from sqlalchemy.orm import Session

from app.models.survey import AppSetting

POPUPS = ("invite", "install")


def _key(name: str) -> str:
    return f"popup_enabled:{name}"


def enabled(db: Session, name: str) -> bool:
    row = db.get(AppSetting, _key(name))
    return row is None or row.value == "true"


def set_enabled(db: Session, name: str, on: bool) -> None:
    """commit은 부르는 쪽에서."""
    row = db.get(AppSetting, _key(name))
    value = "true" if on else "false"
    if row is None:
        db.add(AppSetting(key=_key(name), value=value))
    else:
        row.value = value
