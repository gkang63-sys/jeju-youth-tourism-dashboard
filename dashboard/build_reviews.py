"""naver_blog_posts.json을 규칙으로 분류해 대시보드가 쓰는 reviews.js를 만든다.

분류 근거는 제목과 요약문뿐이다. 해시태그는 경험 서술이 아니므로 분류에서 뺀다.
원본 글은 지우지 않고, 제주 여행과 무관해 보이는 글은 표시만 해서 집계에서 제외한다.
사용법: python build_reviews.py
"""
import json, os, re, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))

ACTIVITIES = [
    ("food", "맛집·향토 음식", r"맛집|흑돼지|고기국수|갈치|해장국|횟집|김밥|몸국|고등어"),
    ("cafe", "카페·디저트", r"카페|베이커리|디저트"),
    ("hike", "오름·숲길·등산", r"오름|한라산|등반|등산|트레킹|올레길|올레 ?\d|숲길|둘레길|사려니|비자림"),
    ("beach", "해변·물놀이", r"해변|해수욕장|스노클링|서핑|다이빙|패들보드|물놀이"),
    ("stay", "호텔·리조트·펜션", r"호캉스|호텔|리조트|펜션|풀빌라|인피니티풀"),
    ("guest", "게스트하우스·파티·혼술바", r"게스트하우스|게하|파티|혼술"),
    ("solo", "혼자 여행", r"혼자|혼여행|혼행|나홀로"),
    ("market", "시장·소품샵", r"동문시장|동문재래시장|올레시장|오일장|오일시장|야시장|소품샵"),
    ("culture", "전시·테마 명소", r"아르떼뮤지엄|박물관|미술관|전시|아쿠아플라넷|테마파크|승마|카트|민속촌|식물원"),
    ("drive", "렌터카·드라이브", r"드라이브|렌터카|렌트카"),
    ("walk", "뚜벅이·대중교통", r"뚜벅이|대중교통|버스 ?여행|버스 ?투어"),
    ("photo", "사진·인생샷", r"인생샷|스냅|포토 ?스팟|사진 ?맛집|사진 ?명소"),
]
POSITIVE = r"좋았|좋아요|좋더|좋습니다|만족했|만족스러웠|만족스럽|최고였|행복했|감동|맛있었|맛있어|맛있더|예뻤|멋졌|아름다웠|친절했|친절하|깨끗했|깨끗하|편했|편하게|편리했|합리적|가성비 ?(좋|최고|굿|갑)|힐링|재방문|또 가고|다시 오고|다시 가고|괜찮았|훌륭"
# 경험 서술이 아니라 안내·권유·가정인 문장
ADVICE = r"추천 대상|찾고 있다면|싶다면|싶으시다면|계획한다면|계획 중이|계획하신다면|원하시는|보시길|들러보세요|방문해 ?보세요|찾으신다면|찾는다면|여행객에게|분들께|다면|하시면|수도 있|수 있|좋은 글|거르시|\?$"
SATISFACTIONS = [
    ("view", "풍경·바다 전망", r"풍경|바다|오션뷰|노을|일출|경치|자연|뷰가"),
    ("taste", "음식 맛", r"맛있|음식|흑돼지|고기국수|갈치|식사|조식"),
    ("facility", "숙소·시설", r"숙소|호텔|객실|침구|수영장|시설|깨끗"),
    ("kind", "친절한 응대", r"친절"),
    ("value", "가성비·가격", r"가성비 ?(좋|최고|굿|갑)|합리적|저렴해|저렴했|저렴하고|착한 가격|가격도 좋|가격이 좋"),
    ("mood", "분위기·여유", r"분위기|힐링|여유|감성|조용"),
    ("move", "이동·위치 편의", r"동선|접근성|교통|위치|주차|공항 ?근처|가까"),
    ("company", "함께한 사람과 추억", r"추억|친구들?과|친구랑|함께한|함께 한"),
]
ISSUES = [
    ("cost", "비용·물가 부담", r"비싸|바가지|(?<!선)물가|비용이 부담|가격이 부담|가격대가 높|가격이 높"),
    ("wait", "대기·혼잡", r"웨이팅이? ?(길|많|오래|심)|대기 ?(시간)?이? ?(길|많|오래)|줄이 길|붐비|혼잡|사람이 너무 많|오래 기다"),
    ("weather", "날씨·결항", r"강풍|비바람|태풍|결항|날씨[^.]{0,12}(아쉬|안 ?좋|나빴|궂|흐렸|변덕)|비가 (많이|계속|엄청)|비 엄청|너무 (추웠|더웠)|난기류"),
    ("transit", "이동·교통·주차", r"(버스|대중교통|배차|이동|교통|운전|렌터카|렌트카)[^.]{0,14}(불편|힘들|어렵|오래 걸|번거|무서)|주차[^.]{0,10}(불편|어렵|힘들|협소|좁|없)"),
    ("room", "숙소·시설 불만", r"(숙소|객실|방음|시설|화장실|욕실|침구|방이|룸)[^.]{0,14}(불편|아쉬|좁|냄새|더럽|낡|소음|시끄|실망|별로)|(?<![무저])소음|(?<!얼레)벌레"),
    ("service", "음식·응대 실망", r"불친절|(맛|음식|식당|서비스|응대|직원)[^.]{0,12}(실망|아쉬|별로|불쾌)"),
    ("other", "기타 아쉬움·실망", r"아쉬웠|아쉬운 점|실망|불편했|불편함|불편하|별로였|후회"),
]
NEGATED = r"(없이|없었|없어|없는|없을|없다|없습|없더|않|아니|안 ?불편|전혀|별로 없|지 ?\.?\.?\.?$)"
NOT_COMPLAINT = r"떠나|돌아가|돌아오|마지막|헤어|일정이 짧|아쉬웠던 마음|아쉬운 마음|아쉬움을 달|마음도|마음을|아쉬울 ?때|아쉬운 분|아쉬운 사람|불편한 분|불편하신 분|불편하셨|불편하면|불편한 일행|발이 불편|몸이 불편|거동|걱정|합리적|비해|단정|좋을 때|안 좋으면|들었지만|후기가 있는|얘기가 많|대신|해외|비싸다고 들|최소화|살피|부위|다르게|덜어|줄여|해소|없애|불편함[이을]?$|않으|불편한가요|일본|이야기를"
SPONSOR = r"협찬(?!성)|원고료|제공받아|제공 받아|제공받았|제공 받았|제공받습니다|지급받습니다|지원받아|지원 받아|지원받았|체험단(?! ?리뷰| ?신청|/기자단)|소정의|유료 ?광고|광고 ?포함|광고입니다|파트너스 활동|활동의 일환"
SPONSOR_NEG = r"^.{0,12}(아니|아님|없이|없는|없음|없습|X\b|x\b|❌|받으면|들어올까|글,)"
TRAVEL = r"여행|후기|코스|숙소|맛집|카페|투어|렌트|렌터카|호텔|리조트|펜션|게스트하우스|오름|해변|해수욕장|일정|뚜벅이|가볼만한|관광|올레"
JEJU_TITLE = r"제주|서귀포|애월|협재|함덕|성산|우도|중문|한림|월정리|표선|한라산|jeju"
NOT_TRAVEL = r"제주항공|제주은행|제주도횟집|제주맥주|제주 ?유나이티드|유럽|발리|후쿠오카|오사카|도쿄|일본|베트남|다낭|푸꾸옥|태국|몽골|실종|추락|사건|절도|구속|검거|프로필|레깅스|기죽이|대상포진|미용실|쇼핑몰|맛집블로거|이주 이야기"
# 연령이 아닌 '20대': 선거 회차, 대수를 세는 표현
AGE_NOISE = r"제 ?20대|20대 ?(대통령|대선|국회|총선)|(CCTV|씨씨티비|주차[^.]{0,8}|차량|카메라|자전거|버스|모니터|렌터카|자리|비행기|차가 한)[^.]{0,6}20대|약 ?(10-)?20대|20대[^.]{0,6}(주차|가능)"
# 여행자 본인이나 일행을 20대로 표현한 말 (제목에 있으면 제목 전체가 그 글의 소개로 본다)
AGE_SELF = r"20대인 나|제가 20대(?! ?초반)|저 20대|저는 20대|저도 20대|나는 20대|나도 20대(?!에)|20대 여자이다보니|20대 평범한|좋은 20대|벌써 20대|20대 ?마지막|20대의 마지막|마지막 20대|20대 ?끝자락|20대의 끝자락|20대 막바지|한 번뿐인 20대|20대끼리|20대 여자 ?\d|서로 20대|20대 중반이 되도록|전부 20대|이때는 20대"
AGE_TITLE_NOT = r"20대 ?(때|시절|초반에|부터)|20대처럼|20대 같|20대 청춘은 아니|라인이 20대|(4|5|6|7)0대"
# 여행 경험담보다 안내에 가까운 제목
GUIDE_TITLE = r"예산표|견적표|가이드|꿀팁|어디로 갈까|기준|이유|완벽 비교|루트 추천|감성 루트|코스 공개|핫플 코스|필수 코스|가볼만한"


LIVED = r"(았|었|했|웠)(다|어|음|습|네|던|더)|더라|ㅠ"


def strip_tags(text):
    return re.sub(r"#\S+", " ", text)


def clauses(post):
    desc = strip_tags(post["desc"])
    parts = re.split(r"\.{2,}|…|(?<=[.!?~])\s+|[!?]+|ㅎㅎ+|ㅋㅋ+", desc)
    return [strip_tags(post["title"]).strip()] + [p.strip() for p in parts if p.strip()]


def is_relevant(post):
    title, desc = post["title"], post["desc"]
    all_text = title + " " + desc
    if not re.search(TRAVEL, all_text) or re.search(NOT_TRAVEL, title):
        return False
    if re.search(JEJU_TITLE, title, re.I):
        return True
    return bool(re.search(r"제주 ?여행|제주도 ?여행", strip_tags(desc)))


def age_mention(post):
    """none: '20대' 없음 / noise: 연령이 아닌 표현 / direct: 여행자 본인·일행을 20대로 표현 / other: 회상·제3자 등 그 밖의 언급"""
    title = post["title"]
    desc = strip_tags(post["desc"])
    if "20대" not in title + desc:
        return "none"
    if "20대" not in re.sub(AGE_NOISE, " ", title + " " + desc):
        return "noise"
    t = re.sub(AGE_NOISE, " ", title)
    if "20대" in t and not re.search(AGE_TITLE_NOT, t):
        return "direct"
    if re.search(AGE_SELF, re.sub(AGE_NOISE, " ", desc)):
        return "direct"
    return "other"


def sponsor_status(post):
    """표시 있음(suspect) / 부정 표현뿐(denied, '협찬 아니고' 등) / 없음(none)"""
    text = post["title"] + " " + post["desc"]
    found = False
    for m in re.finditer(SPONSOR, text):
        found = True
        if not re.search(SPONSOR_NEG, text[m.end():m.end() + 14]):
            return "suspect"
    return "denied" if found else "none"


def first_clause(post, pattern, extra=None, negate=False):
    for c in clauses(post):
        for m in re.finditer(pattern, c):
            if extra and (not re.search(extra, c) or re.search(ADVICE, c)):
                continue
            if negate:
                if re.search(NEGATED, c[m.start():m.end() + 16]) or re.search(NOT_COMPLAINT, c) or re.search(ADVICE, c):
                    continue
            return c
    return None


def excerpt(clause, pattern, size=70):
    if len(clause) <= size:
        return clause
    m = re.search(pattern, clause)
    at = max(0, (m.start() if m else 0) - size // 2)
    return ("…" if at else "") + clause[at:at + size] + "…"


def classify(post):
    labels = {}
    for key, _, pat in ACTIVITIES:
        c = first_clause(post, pat)
        if c:
            labels["a:" + key] = excerpt(c, pat)
    for key, _, pat in SATISFACTIONS:
        c = first_clause(post, pat, extra=POSITIVE)
        if c:
            labels["s:" + key] = excerpt(c, pat)
    specific = False
    for key, _, pat in ISSUES:
        if key == "other" and specific:
            continue
        c = first_clause(post, pat, negate=True)
        if c:
            labels["i:" + key] = excerpt(c, pat)
            specific = True
    return labels


def is_guide(post):
    return bool(re.search(GUIDE_TITLE, post["title"]))


def evidence_key(row, seq, code):
    """근거 글 순서: '20대' 언급, 경험담, 경험을 쓴 문장을 앞세우고 같으면 최신 글부터"""
    rank = (0 if row["age"] == "direct" else 1) + (2 if is_guide(row["post"]) else 0)
    if code[0] != "a" and not re.search(LIVED, row["labels"][code]):
        rank += 4
    return (rank, -int(row["post"]["date"]), seq)


def month_index(date):
    return (int(date[:4]) - 2024) * 12 + int(date[4:6]) - 1


def load_posts():
    with open(os.path.join(HERE, "naver_blog_posts.json"), encoding="utf-8") as fh:
        return json.load(fh)


def analyse(raw):
    rows = []
    for p in raw["posts"]:
        rel = is_relevant(p)
        rows.append({"post": p, "relevant": rel, "age": age_mention(p), "sponsor": sponsor_status(p), "labels": classify(p) if rel else {}})
    return rows


def main():
    raw = load_posts()
    rows = analyse(raw)
    taxonomy = {
        "a": [[k, n] for k, n, _ in ACTIVITIES],
        "s": [[k, n] for k, n, _ in SATISFACTIONS],
        "i": [[k, n] for k, n, _ in ISSUES],
    }
    months, themes, candidates = {}, {}, {}
    relevant = 0
    for seq, r in enumerate(rows):
        p = r["post"]
        if not r["relevant"] or not p["link"].startswith(("https://", "http://")):
            continue
        relevant += 1
        m = month_index(p["date"])
        direct, suspect = r["age"] == "direct", r["sponsor"] == "suspect"
        complaint_only = p["groups"] == ["complaint"]
        mm = months.setdefault(m, {"total": 0, "young": 0, "other": 0, "suspect": 0, "youngSuspect": 0, "youngGuide": 0, "pool": 0, "poolYoung": 0})
        mm["total"] += 1
        mm["young"] += direct
        mm["other"] += r["age"] == "other"
        mm["suspect"] += suspect
        mm["youngSuspect"] += direct and suspect
        mm["youngGuide"] += direct and is_guide(p)
        mm["pool"] += not complaint_only
        mm["poolYoung"] += direct and not complaint_only
        for code in r["labels"]:
            kind = code[0]
            # 불만 검색어로만 모은 글은 활동·만족 건수와 근거에 넣지 않는다
            if kind != "i" and complaint_only:
                continue
            cell = themes.setdefault(code, {}).setdefault(m, [0, 0, 0])
            cell[0] += 1
            cell[1] += direct
            cell[2] += suspect
            if not suspect:
                candidates.setdefault((code, m), []).append((evidence_key(r, seq, code), seq, r))
    # 항목·월마다 상위 5건만 남긴다. 어떤 기간을 골라도 그 기간의 상위 5건은 이 안에 있다
    posts, post_index, evidence = [], {}, {}
    for (code, m), items in sorted(candidates.items()):
        for key, seq, r in sorted(items, key=lambda x: x[0])[:5]:
            p = r["post"]
            if seq not in post_index:
                post_index[seq] = len(posts)
                posts.append({"t": p["title"][:60], "u": p["link"], "d": p["date"], "y": r["age"] == "direct"})
            evidence.setdefault(code, []).append([m, key[0], post_index[seq], seq, r["labels"][code]])
    out = {
        "collected": raw["collected"], "range": raw["range"],
        "firstDate": raw["posts"][0]["date"], "lastDate": raw["posts"][-1]["date"],
        "totalPosts": len(rows), "relevantPosts": relevant,
        "excludedPosts": sum(not r["relevant"] for r in rows),
        "suspectAll": sum(r["sponsor"] == "suspect" for r in rows),
        "deniedAll": sum(r["sponsor"] == "denied" for r in rows),
        "returned": raw["returned_total"], "taxonomy": taxonomy,
        "months": months, "themes": themes, "posts": posts, "evidence": evidence,
    }
    with open(os.path.join(HERE, "reviews.js"), "w", encoding="utf-8") as fh:
        fh.write("window.REVIEWS=")
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";")
    print("전체", len(rows), "관련", relevant, "남긴 근거 글", len(posts), "제외", out["excludedPosts"], "협찬 의심", out["suspectAll"], "부정 표현", out["deniedAll"])
    print("reviews.js", round(os.path.getsize(os.path.join(HERE, "reviews.js")) / 1048576, 2), "MB")


if __name__ == "__main__":
    main()
