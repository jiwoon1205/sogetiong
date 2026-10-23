"""기본 데이터 넣기: 학교·캠퍼스·학과·관심사·관리자 역할.

실행: python -m app.scripts.seed
여러 번 실행해도 안전하다. 서버가 시작할 때마다 자동으로 실행된다 (Dockerfile).

학교 (2026-10-24 경희대 추가): 아래 SCHOOLS. 한국외대는 항상 열려 있고, 다른 학교는 설정 OPEN_SCHOOLS에
메일 주소 뒷부분(khu.ac.kr)을 적어야 열린다 → 서버가 시작할 때 여기서 universities.active를 맞춘다.

한국외대 학과 목록: 프로젝트 문서 "한국외대 학과 목록 초안 (2026-09-29)" 기준.
- 학교 홈페이지 단과대학 페이지 표기 그대로
- 2017년 이후 모집중지 학과(통번역대학·국제지역대학·지식콘텐츠학부)는 재학생이 있어 포함
- 2016년 이전 모집중지 학과, 확인이 필요한 학과는 제외 (문의가 오면 여기에 추가)
- 학부 안의 트랙은 하나의 과, 전공별로 입학하는 곳(외국어교육학부 ○○전공 등)은 따로

목록에 없는 학과는 삭제하지 않고 비활성화(active=False)한다.
→ 새로 고를 수 없지만, 이미 그 학과를 고른 사용자의 데이터는 깨지지 않는다.
목록에 학과를 추가하려면 아래 학교의 캠퍼스 목록에 이름을 넣고 서버를 다시 시작하면 된다.

경희대 학과 목록: 프로젝트 문서 "경희대 학과 목록 초안 (2026-10-24)" 기준.
- 2026·2024학년도 수시모집요강 모집단위 (이름이 바뀐 학과의 재학생도 찾을 수 있게 두 해를 같이 봄)
- 학부·계열로 들어와 나중에 학과를 고르는 곳은 한 칸 (학과를 바꿀 수 없어서, 1학년 때 고른 이름이 계속 맞아야 함)
- 이름이 바뀐 학과는 새 이름 옆에 옛 이름을 괄호로. 예과·본과는 한 칸
- 재직자 전형 학과·대학원은 뺌 (문의가 오면 추가)
"""

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.admin import ROLE_PERMISSIONS, AdminRole
from app.models.profile import Interest
from app.models.university import Campus, Department, University

HUFS_CAMPUSES: dict[str, list[str]] = {
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

KHU_CAMPUSES: dict[str, list[str]] = {
    "서울캠퍼스": [
        # 자율전공
        "자율전공학부(서울)",
        # 문과대학
        "국어국문학과", "영어영문학과", "응용영어통번역학과", "사학과", "철학과",
        # 정경대학
        "정치외교학과", "행정학과", "사회학과", "경제학과", "무역학과", "미디어학과",
        # 경영대학
        "경영학과·회계학과 (경영회계계열, 회계·세무학과)", "빅데이터응용학과",
        # 호텔관광대학
        "Hospitality경영학과", "조리&푸드디자인학과", "관광·엔터테인먼트학부 (관광학과·문화엔터테인먼트학과)", "글로벌Hospitality·관광학과",
        # 생활과학대학
        "아동가족학과", "주거환경학과", "의상학과", "식품영양학과",
        # 이과대학
        "수학과", "물리학과", "화학과", "생물학과", "지리학과", "미래정보디스플레이학부 (정보디스플레이학과)",
        # 의과대학 · 한의과대학 · 치과대학 (예과·본과 한 칸)
        "의예과·의학과", "한의예과·한의학과", "치의예과·치의학과",
        # 약학대학
        "약학과", "한약학과", "약과학과",
        # 간호과학대학
        "간호학과",
        # 음악대학 (정시만 뽑지만 재학생 있음)
        "작곡과", "성악과", "기악과",
        # 미술대학 · 무용학부
        "미술학부", "무용학부",
    ],
    "국제캠퍼스": [
        # 자유전공
        "자유전공학부(국제)",
        # 외국어대학
        "프랑스어학과", "스페인어학과", "러시아어학과", "중국어학과", "일본어학과", "한국어학과", "글로벌커뮤니케이션학부",
        # 국제대학
        "국제학과",
        # 공과대학
        "기계공학부 (기계공학과)", "산업경영공학과", "원자력공학과", "화학공학과", "신소재공학과 (정보전자신소재공학과)",
        "사회기반시스템공학과", "건축공학과", "환경학및환경공학과", "건축학과",
        # 전자정보대학
        "전자공학부 (전자공학과·반도체공학과)", "생체의공학과",
        # 소프트웨어융합대학
        "컴퓨터공학부 (컴퓨터공학과·인공지능학과)", "소프트웨어융합학과",
        # 응용과학대학
        "응용수학과", "응용물리학과", "응용화학과", "우주과학과",
        # 생명과학대학
        "유전생명공학과", "식품생명공학과", "스마트팜과학과", "융합바이오·신소재공학과", "한방생명공학과", "식물·환경신소재공학과",
        # 예술·디자인대학
        "산업디자인학과", "시각디자인학과", "환경조경디자인학과", "의류디자인학과", "디지털콘텐츠학과", "도예학과", "연극영화학과", "PostModern음악학과",
        # 체육대학
        "체육학과", "스포츠의학과", "골프산업학과", "스포츠지도학과", "태권도학과",
    ],
}

# always_open: 설정과 상관없이 항상 열림. 아니면 OPEN_SCHOOLS에 email_domain이 있어야 열림.
SCHOOLS = [
    {"name": "한국외국어대학교", "email_domain": "hufs.ac.kr", "always_open": True, "campuses": HUFS_CAMPUSES},
    {"name": "경희대학교", "email_domain": "khu.ac.kr", "always_open": False, "campuses": KHU_CAMPUSES},
]

# 예전 이름 호환 (한국외대 목록)
CAMPUSES = HUFS_CAMPUSES

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


def sync_schools(db) -> None:
    """학교·캠퍼스·학과를 맞추고, 학교를 열고 닫는다 (OPEN_SCHOOLS)."""
    open_domains = get_settings().open_school_domains
    for school in SCHOOLS:
        uni = db.query(University).filter(University.email_domain == school["email_domain"]).first()
        if uni is None:
            uni = University(name=school["name"], email_domain=school["email_domain"])
            db.add(uni)
            db.flush()
        uni.active = school["always_open"] or school["email_domain"] in open_domains

        for campus_name, departments in school["campuses"].items():
            campus = db.query(Campus).filter(Campus.university_id == uni.id, Campus.name == campus_name).first()
            if campus is None:
                campus = Campus(university_id=uni.id, name=campus_name)
                db.add(campus)
                db.flush()
            sync_departments(db, campus, departments)


def run() -> None:
    db = SessionLocal()
    try:
        sync_schools(db)

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
