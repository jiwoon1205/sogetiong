"""기본 데이터 넣기: 학교·캠퍼스·학과·관심사·관리자 역할.

실행: python -m app.scripts.seed
여러 번 실행해도 이미 있는 데이터는 건너뛴다.

⚠️ 학과 목록은 예시다. 실제 학과 목록으로 바꿔서 사용할 것.
"""

from app.db.session import SessionLocal
from app.models.admin import ROLE_PERMISSIONS, AdminRole
from app.models.profile import Interest
from app.models.university import Campus, Department, University

UNIVERSITY = {"name": "한국외국어대학교", "email_domain": "hufs.ac.kr"}

# TODO: 실제 학과 목록으로 교체
CAMPUSES = {
    "서울캠퍼스": ["영어학과", "경영학과", "경제학과", "미디어커뮤니케이션학부", "Language & AI 융합학부"],
    "글로벌캠퍼스": ["컴퓨터공학부", "통계학과", "국제금융학과", "바이오메디컬공학부"],
}

INTERESTS = [
    "카페", "영화", "여행", "운동", "음악", "독서", "게임", "요리", "사진", "전시",
    "공연", "맛집", "등산", "산책", "드라마", "애니메이션", "외국어", "코딩", "반려동물", "패션",
]


def run() -> None:
    db = SessionLocal()
    try:
        uni = db.query(University).filter(University.email_domain == UNIVERSITY["email_domain"]).first()
        if uni is None:
            uni = University(**UNIVERSITY)
            db.add(uni)
            db.flush()

        for campus_name, departments in CAMPUSES.items():
            campus = db.query(Campus).filter(Campus.university_id == uni.id, Campus.name == campus_name).first()
            if campus is None:
                campus = Campus(university_id=uni.id, name=campus_name)
                db.add(campus)
                db.flush()
            for dept_name in departments:
                exists = db.query(Department.id).filter(Department.campus_id == campus.id, Department.name == dept_name).first()
                if not exists:
                    db.add(Department(campus_id=campus.id, name=dept_name))

        existing = {name for (name,) in db.query(Interest.name)}
        db.add_all([Interest(name=n) for n in INTERESTS if n not in existing])

        for role_name, permissions in ROLE_PERMISSIONS.items():
            role = db.query(AdminRole).filter(AdminRole.name == role_name).first()
            if role is None:
                db.add(AdminRole(name=role_name, permissions_json=permissions))
            else:
                role.permissions_json = permissions  # 코드의 권한표를 기준으로 맞춘다

        db.commit()
        print("seed 완료")
    finally:
        db.close()


if __name__ == "__main__":
    run()
