"""NAVER API HUB의 블로그 검색 API로 제주 여행 후기 검색 결과를 모아 naver_blog_posts.json에 저장한다.

키는 같은 폴더의 .env(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)에서만 읽고, 어디에도 출력하거나 저장하지 않는다.
API는 본문이 아니라 제목과 요약문만 돌려준다. 작성자 이름은 쓰지 않으므로 저장하지 않는다.

사용법: python collect_reviews.py --check   인증만 1회 확인
        python collect_reviews.py           전체 수집
"""
import html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
QUERIES = {
    "general": ["제주 여행 후기", "제주도 여행 후기", "제주 여행 솔직 후기", "제주 여행 내돈내산 후기", "제주 여행 코스 후기", "제주 혼자 여행 후기", "제주 우정 여행 후기", "제주 커플 여행 후기", "제주 뚜벅이 여행 후기", "제주 가족 여행 후기"],
    "young": ["20대 제주 여행 후기", "20대 제주도 여행", "대학생 제주 여행 후기", "청년 제주 여행 후기", "20대 여자 제주 여행", "20대 친구 제주 여행"],
    "complaint": ["제주 여행 아쉬웠던 점", "제주 여행 불편했던 점", "제주 여행 실망 후기", "제주 여행 비싸다 후기"],
}
SORTS = ["sim", "date"]
FIRST, LAST = "20240101", "20261031"


def load_keys():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        raise SystemExit(".env 파일이 없습니다. .env.example을 .env로 복사한 뒤 키를 넣으세요")
    keys = {}
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip().strip("'\"")
    cid, secret = keys.get("NAVER_CLIENT_ID"), keys.get("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit(".env에 NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 없습니다")
    return cid, secret


def call(query, start, sort, cid, secret):
    url = API + "?" + urllib.parse.urlencode({"query": query, "display": 100, "start": start, "sort": sort, "format": "json"})
    req = urllib.request.Request(url, headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res)


def error_code(err):
    try:
        return json.loads(err.read().decode("utf-8", "replace")).get("errorCode", "알 수 없음")
    except ValueError:
        return "알 수 없음"


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def check(cid, secret):
    try:
        data = call(QUERIES["general"][0], 1, "sim", cid, secret)
    except urllib.error.HTTPError as err:
        print("인증 실패: HTTP", err.code, "오류 코드", error_code(err))
        return 1
    except urllib.error.URLError as err:
        print("연결 실패:", type(err.reason).__name__)
        return 1
    print("인증 성공: 응답", len(data.get("items", [])), "건")
    return 0


def collect(cid, secret):
    posts, calls, out_of_range, stats = {}, 0, 0, []
    for group, queries in QUERIES.items():
        for q in queries:
            row = {"group": group, "query": q, "api_total": None, "returned": 0, "in_range": 0, "new_unique": 0}
            for sort in SORTS:
                for start in range(1, 1000, 100):
                    try:
                        data = call(q, start, sort, cid, secret)
                    except urllib.error.HTTPError as err:
                        print("수집 중단: HTTP", err.code, "오류 코드", error_code(err), "| 검색어", q)
                        return 1
                    calls += 1
                    row["api_total"] = data.get("total")
                    items = data.get("items", [])
                    row["returned"] += len(items)
                    for it in items:
                        d = it.get("postdate", "")
                        if not FIRST <= d <= LAST:
                            out_of_range += 1
                            continue
                        row["in_range"] += 1
                        if it["link"] not in posts:
                            posts[it["link"]] = {"link": it["link"], "date": d, "title": clean(it["title"]), "desc": clean(it["description"]), "groups": [], "queries": []}
                            row["new_unique"] += 1
                        p = posts[it["link"]]
                        if group not in p["groups"]:
                            p["groups"].append(group)
                        if q not in p["queries"]:
                            p["queries"].append(q)
                    time.sleep(0.12)
                    if len(items) < 100:
                        break
            stats.append(row)
            print(f"{q}: 받은 결과 {row['returned']} / 기간 안 {row['in_range']} / 새 글 {row['new_unique']}", flush=True)
    out = {"collected": date.today().isoformat(), "source": "네이버 검색 API (블로그)", "queries": QUERIES, "sorts": SORTS, "range": [FIRST, LAST], "api_calls": calls, "returned_total": sum(r["returned"] for r in stats), "out_of_range_results": out_of_range, "query_stats": stats, "posts": sorted(posts.values(), key=lambda p: p["date"])}
    with open(os.path.join(HERE, "naver_blog_posts.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    print("호출", calls, "받은 결과", out["returned_total"], "기간 밖", out_of_range, "중복 제거 후", len(posts))
    return 0


if __name__ == "__main__":
    cid, secret = load_keys()
    sys.exit(check(cid, secret) if "--check" in sys.argv else collect(cid, secret))
