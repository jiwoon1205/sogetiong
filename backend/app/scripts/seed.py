"""기본 데이터 넣기: 학교·캠퍼스·학과·관심사·관리자 역할.

실행: python -m app.scripts.seed
여러 번 실행해도 안전하다. 서버가 시작할 때마다 자동으로 실행된다 (Dockerfile).

학과 목록: 프로젝트 문서 "한국외대 학과 목록 초안 (2026-09-29)" 기준.
- 학교 홈페이지 단과대학 페이지 표기 그대로
- 2017년 이후 모집중지 학과(통번역대학·국제지역대학·지식콘텐츠학부)는 재학생이 있어 포함
- 2016년 이전 모집중지 학과, 확인이 필요한 학과는 제외 (문의가 오면 여기에 추가)
- 학부 안의 트랙은 하나의 과, 전공별로 입학하는 곳(외국어교육학부 ○○전공 등)은 따로

목록에 없는 학과는 삭제하지 않고 비활성화(active=False)한다.
→ 새로 고를 수 없지만, 이미 그 학과를 고른 사용자의 데이터는 깨지지 않는다.
목록에 학과를 추가하려면 아래 CAMPUSES에 이름을 넣고 서버를 다시 시작하면 된다.
"""

from app.db.session import SessionLocal
from app.models.admin import ROLE_PERMISSIONS, AdminRole
from app.models.profile import Interest
from app.models.university import Campus, Department, University

UNIVERSITY = {"name": "한국외국어대학교", "email_domain": "hufs.ac.kr"}

CAMPUSES: dict[str, list[str]] = {
    "서울캠퍼스": [
        # 영어대학
        "ELLT학과", "영미문학·문화학과", "영어통번역(EICC)학과",
        # 서양어대학
        "프랑스어학부", "독일어과", "노어과", "스페인어과", "이탈리아어과", "포르투갈어과", "네덜란드어과", "스칸디나비아어과",
        # 아시아언어문화대학
        "말레이·인도네시아어과", "아랍어과", "태국학과", "베트남어과", "인도어과", "튀르키예·아제르바이잔학과", "페르시아어·이란학과", "몽골어과",
        # 중국학대학
        "중국언어문화학부", "중국외교통상학부",
        # 일본학대학
        "일본언어문화학부", "융합일본지역학부",
        # 사회과학대학
        "정치외교학과", "행정학과", "미디어커뮤니케이션학부",
        # 상경대학
        "국제통상학과", "경제학부",
        # 경영대학
        "경영학부",
        # 사범대학
        "영어교육과", "한국어교육과", "외국어교육학부 프랑스어교육전공", "외국어교육학부 독일어교육전공", "외국어교육학부 중국어교육전공",
        # AI융합대학
        "Language & AI융합학부", "Social Science & AI융합학부",
        # 학부 (단과대학 소속 없음)
        "국제학부", "Language & Diplomacy학부", "Language & Trade학부", "자유전공학부(서울)",
        # 2026-10-09 추가 (사용자 요청)
        "KFL학부 외국어로서의한국어통번역전공", "동북아외교통상",
    ],
    "글로벌캠퍼스": [
        # 인문대학
        "철학과", "사학과", "언어인지과학과", "지식콘텐츠학부",
        # 통번역대학 (모집중지, 재학생 있음)
        "영어통번역학부", "독일어통번역학과", "스페인어통번역학과", "이탈리아어통번역학과", "중국어통번역학과",
        "일본어통번역학과", "아랍어통번역학과", "말레이·인도네시아어통번역학과", "태국어통번역학과",
        # 국가전략언어대학
        "폴란드학과", "루마니아학과", "체코·슬로바키아학과", "헝가리학과", "세르비아·크로아티아학과",
        "그리스·불가리아학과", "중앙아시아학과", "아프리카학부", "우크라이나학과", "한국학과",
        # 국제지역대학 (모집중지, 재학생 있음)
        "프랑스학과", "브라질학과", "인도학과", "러시아학과", "국제스포츠레저학부",
        # 경상대학
        "Global Business & Technology학부", "국제금융학과",
        # 자연과학대학
        "수학과", "통계학과", "전자물리학과", "환경학과", "생명공학과", "화학과",
        # 공과대학
        "컴퓨터공학부", "정보통신공학과", "반도체전자공학부 반도체공학전공", "반도체전자공학부 전자공학전공", "산업경영공학과",
        # 융합인재대학
        "융합인재학부",
        # Culture & Technology융합대학
        "글로벌스포츠산업학부", "디지털콘텐츠학부", "투어리즘 & 웰니스학부",
        # AI융합대학
        "AI데이터융합학부", "Finance & AI융합학부",
        # 학부 (단과대학 소속 없음)
        "바이오메디컬공학부", "기후변화융합학부", "자유전공학부(글로벌)",
    ],
}

INTERESTS = [
    "카페", "영화", "여행", "운동", "음악", "독서", "게임", "요리", "사진", "전시",
    "공연", "맛집", "등산", "산책", "드라마", "애니메이션", "외국어", "코딩", "반려동물", "패션",
]


def sync_departments(db, campus: Campus, names: list[str]) -> None:
    """목록에 있는 학과는 추가·활성화, 목록에 없는 학과는 비활성화 (삭제하지 않음)."""
    wanted = set(names)
    existing = {d.name: d for d in db.query(Department).filter(Department.campus_id == campus.id)}
    for name in names:
        dept = existing.get(name)
        if dept is None:
            db.add(Department(campus_id=campus.id, name=name))
        elif not dept.active:
            dept.active = True
    for name, dept in existing.items():
        if name not in wanted and dept.active:
            dept.active = False


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
            sync_departments(db, campus, departments)

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
