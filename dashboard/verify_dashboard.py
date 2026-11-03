"""대시보드를 실제 브라우저로 열어 필터를 조작하고, 화면 수치를 원본 엑셀에서 따로 계산한 값과 대조한다.

필요: pip install playwright, 설치된 Chrome (data.js 집계 코드를 쓰지 않고 원본을 다시 읽어 계산한다)
사용법: python verify_dashboard.py [스크린샷 폴더]
"""
import importlib.util, json, os, re, sys, zipfile, posixpath
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def read(name, sheet=None):
    with zipfile.ZipFile(os.path.join(ROOT, name)) as z:
        shared = []
        with z.open("xl/sharedStrings.xml") as fh:
            for _, el in ET.iterparse(fh):
                if el.tag == M + "si":
                    shared.append("".join(t.text or "" for t in el.iter(M + "t")))
                    el.clear()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall(PR + "Relationship")}
        t = next(rels[s.get(R + "id")] for s in wb.find(M + "sheets") if sheet is None or s.get("name") == sheet)
        path = t.lstrip("/") if t.startswith("/") else posixpath.normpath("xl/" + t)
        rows = []
        with z.open(path) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag != M + "row":
                    continue
                row = {}
                for c in el.findall(M + "c"):
                    v = c.find(M + "v")
                    if v is None or v.text is None:
                        continue
                    ref = re.match(r"[A-Z]+", c.get("r")).group()
                    if c.get("t") == "s":
                        row[ref] = shared[int(v.text)]
                    elif c.get("t") == "str":
                        row[ref] = v.text
                    else:
                        n = float(v.text)
                        row[ref] = int(n) if n.is_integer() else n
                el.clear()
                rows.append(row)
    return rows[1:]


print("원본 읽는 중...", flush=True)
AGE = read("제주 연령대별 방문.xlsx")
INB = read("월별 입도 관광객.xlsx")
EMD = read("제주 지역별 방문객(읍면동).xlsx", "제주 지역별 방문객(읍면동)")
VIS = read("비짓제주 검색어 순위.xlsx")
POP = read("제주 지역별 인기 장소.xlsx")
SGG = {r["E"]: r["D"] for r in EMD}
EM = [n for n in SGG if n[-1] in "읍면"]
DG = {n for n in SGG if n[-1] == "동"}
AD = {}
for a in {r["D"] for r in VIS}:
    e = next((n for n in EM if n in a), None) or next((t for t in a.split() if t in DG), None)
    s = "서귀포시" if "서귀포시" in a else "제주시" if "제주시" in a else SGG[e] if e else None
    AD[a] = (s, e)


def ym(i):
    return (2024 + i // 12) * 100 + i % 12 + 1


def region_ok_emd(name, region):
    if region == "all":
        return True
    kind, v = region.split(":")
    return SGG[name] == v if kind == "sgg" else name == v


def expected(sc):
    lo, hi = ym(sc["from"]), ym(sc["to"])
    reg, sex = sc.get("region", "all"), sc.get("sex", "all")
    sexok = lambda r: sex == "all" or r["D"] == sex
    a20 = defaultdict(int)
    allage = 0
    for r in AGE:
        if not sexok(r):
            continue
        if r["E"] == 20:
            a20[r["A"]] += r["F"]
        if lo <= r["A"] <= hi:
            allage += r["F"]
    ms = sorted(m for m in a20 if lo <= m <= hi)
    out = {"total": sum(a20[m] for m in ms), "months": len(ms)}
    out["share"] = out["total"] / allage * 100 if allage else None
    out["mom"] = None
    if ms and ms[-1] - 100 in a20:
        out["mom"] = (a20[ms[-1]] / a20[ms[-1] - 100] - 1) * 100
    pairs = [m for m in ms if m - 100 in a20]
    out["period"] = (sum(a20[m] for m in pairs) / sum(a20[m - 100] for m in pairs) - 1) * 100 if pairs else None
    col = {"tot": "H", "dom": "F", "for": "G"}[sc.get("visitor", "tot")]
    ev = Counter()
    for r in EMD:
        if lo <= r["A"] <= hi:
            ev[r["E"]] += r[col]
    out["regionAll"] = sum(ev.values())
    out["regionSelected"] = sum(v for k, v in ev.items() if region_ok_emd(k, reg))
    ic = {"tot": "D", "dom": "B", "for": "C"}[sc.get("visitor", "tot")]
    out["inbound"] = sum(r[ic] for r in INB if lo <= r["A"] <= hi)
    pm = {"arr": "F", "tour": "H", "res": "I"}[sc.get("arrive", "arr")]
    pc = Counter()
    seen = set()
    t_arr = 0
    for r in POP:
        if not lo <= r["A"] <= hi or not region_ok_emd(r["E"], reg):
            continue
        if sc.get("pcat") and r["G"] != sc["pcat"]:
            continue
        k = (str(r["B"]), r["E"])
        pc[k] += r[pm]
        seen.add(k)
        t_arr += r["F"]
    out["placeCount"] = len(seen)
    out["placeTotal"] = t_arr
    out["placeTop"] = sorted(pc.items(), key=lambda x: -x[1])[:5]
    sc2 = Counter()
    for r in VIS:
        if not lo <= r["A"] <= hi:
            continue
        if sc.get("scat") and r["B"] != sc["scat"]:
            continue
        s, e = AD[r["D"]]
        if reg != "all":
            kind, v = reg.split(":")
            if (kind == "sgg" and s != v) or (kind == "emd" and e != v):
                continue
        sc2[str(r["C"])] += r["E"]
    out["searchTotal"] = sum(sc2.values())
    out["searchCount"] = len(sc2)
    out["searchTop"] = sorted(sc2.items(), key=lambda x: -x[1])[:5]
    return out


SCENARIOS = [
    {"name": "기본", "from": 0, "to": 31},
    {"name": "2025년", "from": 12, "to": 23},
    {"name": "2024년(전년 없음)", "from": 0, "to": 11},
    {"name": "2026-09만(인기 장소만 있음)", "from": 32, "to": 32},
    {"name": "2026 여성 외국인 제주시 관광객 관광지 호텔", "from": 24, "to": 31, "sex": "W", "visitor": "for", "arrive": "tour", "region": "sgg:제주시", "scat": "관광지", "pcat": "호텔"},
    {"name": "애월읍", "from": 0, "to": 31, "region": "emd:애월읍"},
    {"name": "용담2동(동 지역 검색어)", "from": 0, "to": 31, "region": "emd:용담2동", "arrive": "res"},
    {"name": "서귀포시 축제", "from": 12, "to": 31, "region": "sgg:서귀포시", "scat": "축제/행사", "visitor": "dom"},
    {"name": "전체 기간 끝까지", "from": 0, "to": 32},
    {"name": "2026-10만(온라인 후기만 있음)", "from": 33, "to": 33},
]
fails, checks = [], 0


def check(label, got, want, tol=None):
    global checks
    checks += 1
    ok = (abs(got - want) <= tol) if tol is not None and got is not None and want is not None else got == want
    if not ok:
        fails.append(f"{label}: 화면 {got!r} / 원본 {want!r}")


def fmt(n):
    return f"{round(n):,}"


def apply(page, sc):
    page.click("#f-reset")
    page.select_option("#f-from", str(sc["from"]))
    page.select_option("#f-to", str(sc["to"]))
    page.select_option("#f-region", sc.get("region", "all"))
    page.select_option("#f-sex", sc.get("sex", "all"))
    page.select_option("#f-visitor", sc.get("visitor", "tot"))
    page.select_option("#f-arrive", sc.get("arrive", "arr"))
    page.select_option("#f-scat", label=sc.get("scat", "전체"))
    page.select_option("#f-pcat", label=sc.get("pcat", "전체"))


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    url = "file:///" + os.path.join(HERE, "index.html").replace("\\", "/")
    page.goto(url)
    page.wait_for_selector("#map svg")

    for sc in SCENARIOS:
        apply(page, sc)
        ex = expected(sc)
        n = sc["name"]
        txt = lambda i: page.inner_text("#" + i)
        hero = txt("kpi-visitors")
        if ex["months"]:
            check(n + " 20대 합계", fmt(ex["total"]) + "명" in hero, True)
            check(n + " 비중", f"{ex['share']:.1f}%" in txt("kpi-share"), True)
        else:
            check(n + " 20대 없음 안내", "자료 없음" in hero, True)
            check(n + " 선그래프 안내", "자료가 없습니다" in txt("chart-trend"), True)
        mom, per = txt("kpi-mom"), txt("kpi-period")
        check(n + " 전년 동월", f"{abs(ex['mom']):.1f}%" in mom if ex["mom"] is not None else "계산 불가" in mom, True)
        check(n + " 전년 동기", f"{abs(ex['period']):.1f}%" in per if ex["period"] is not None else "계산 불가" in per, True)
        m = page.evaluate("""() => { const m = __dash.model; return {
            total: m.age.total, regionAll: m.region.all, regionSel: m.region.selected, inbound: m.inbound.total,
            placeCount: m.places.ids.length, placeTotal: m.places.tArr, searchTotal: m.search.total, searchCount: m.search.ids.length,
            placeTop: m.places.ids.slice(0,5).map(g => [__dash.P.names[__dash.groupName[g]], __dash.E.names[__dash.groupEmd[g]], m.places.measure[g]]),
            searchTop: m.search.ids.slice(0,5).map(n => [__dash.S.names[n], m.search.sum[n]]) } }""")
        check(n + " 지역 전체", m["regionAll"], ex["regionAll"])
        check(n + " 지역 선택", m["regionSel"], ex["regionSelected"])
        check(n + " 입도", m["inbound"], ex["inbound"])
        check(n + " 장소 수", m["placeCount"], ex["placeCount"])
        check(n + " 장소 도착 합", m["placeTotal"], ex["placeTotal"])
        check(n + " 검색 합", m["searchTotal"], ex["searchTotal"])
        check(n + " 검색어 수", m["searchCount"], ex["searchCount"])
        check(n + " 장소 값 상위", [x[2] for x in m["placeTop"]], [v for _, v in ex["placeTop"]])
        check(n + " 검색 값 상위", [x[1] for x in m["searchTop"]], [v for _, v in ex["searchTop"]])
        if ex["placeCount"]:
            tbl = txt("table-places")
            check(n + " 장소 표 값", fmt(ex["placeTop"][0][1]) in tbl, True)
            check(n + " 쪽 표시", f"/ {ex['placeCount']:,}" in txt("place-pager"), True)
        else:
            check(n + " 장소 안내", "자료가 없습니다" in txt("table-places"), True)
        if ex["searchCount"]:
            check(n + " 워드클라우드 글자", page.locator("#wordcloud svg text").count() > 0, True)
        else:
            check(n + " 검색 안내", "없습니다" in txt("wordcloud"), True)
        if ex["regionAll"]:
            check(n + " 막대 값", fmt(ex["regionSelected"]) + "명" in txt("region-lede"), True)
            fills = page.evaluate("() => [...document.querySelectorAll('#map path.region')].map(p => p.getAttribute('fill'))")
            check(n + " 지도 읍면동 43개", len(fills), 43)
            check(n + " 지도 색 변화", len(set(fills)) > 1, True)
        else:
            check(n + " 지도 안내", "자료가 없습니다" in txt("map"), True)
        print(f"  [{n}] 20대 {ex['total']:,} / 장소 {ex['placeCount']:,}곳 / 검색 {ex['searchTotal']:,} / 1위 {ex['searchTop'][0][0] if ex['searchTop'] else '-'}", flush=True)

    # 조작 동작
    page.click("#f-reset")
    page.click('#map path[data-name="한림읍"]')
    check("지도 클릭 → 지역 필터", page.input_value("#f-region"), "emd:한림읍")
    check("지도 클릭 → 표 갱신", "한림읍" in page.inner_text("#table-places"), True)
    page.click('#map path[data-name="한림읍"]')
    check("지도 다시 클릭 → 해제", page.input_value("#f-region"), "all")
    page.locator("#chart-region g.bar-g").first.click()
    check("막대 클릭 → 지역 필터", page.input_value("#f-region"), "emd:용담2동")
    page.click("#f-reset")
    before = page.inner_text("#table-places")
    page.click("#place-next")
    check("쪽 넘김", page.inner_text("#table-places") != before, True)
    check("쪽 넘김 표시", page.inner_text("#place-range").startswith("11 - 20"), True)
    page.fill("#place-q", "성산일출봉")
    check("장소 검색", "성산일출봉" in page.inner_text("#table-places"), True)
    page.fill("#place-q", "없는이름xyz")
    check("장소 검색 없음 안내", "일치하는" in page.inner_text("#table-places"), True)
    page.fill("#word-q", "한라산")
    check("키워드 검색", "한라산" in page.inner_text("#table-keywords"), True)
    page.click("#f-reset")
    check("초기화 후 검색어 비움", page.input_value("#place-q"), "")
    page.select_option("#f-from", "20")
    page.select_option("#f-to", "5")
    check("기간 역전 시 맞춤", int(page.input_value("#f-from")) <= int(page.input_value("#f-to")), True)
    page.click("#f-reset")
    bx = page.locator("#chart-trend svg").bounding_box()
    page.mouse.move(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    check("선그래프 툴팁", "명" in page.inner_text("#tooltip"), True)
    page.mouse.move(0, 0)
    for sel in ("#chart-trend", "#chart-inbound", "#chart-age", "#chart-region"):
        check(sel + " 축 제목", page.locator(sel + " .axis-title").count() >= 1, True)
    check("표로 보기 토글", page.locator("details.tbl").count(), 4)
    page.locator("details.tbl summary").first.click()
    check("표로 보기 내용", "2026-08" in page.inner_text("#table-trend"), True)
    wide = page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    check("넓은 화면 가로 넘침 없음", wide, True)

    # 묶기 전후 행 수: 지운 행이 없어야 한다
    counts = page.evaluate("() => ({s: __dash.S.cnt.reduce((a, b) => a + b, 0), p: __dash.P.mon.length, e: __dash.E.rows.length, a: __dash.D.age.length, i: __dash.D.inbound.length})")
    check("검색 행 수 보존", counts["s"], len(VIS))
    check("장소 행 수 보존", counts["p"], len(POP))
    check("읍면동 행 수 보존", counts["e"], len(EMD))
    check("연령대 행 수 보존", counts["a"], len(AGE))
    check("입도 행 수 보존", counts["i"], len(INB))

    # 도구 설명과 키보드
    page.locator('#map path[data-name="애월읍"]').hover()
    check("지도 도구 설명", "애월읍" in page.inner_text("#tooltip"), True)
    page.locator("#wordcloud svg text").first.hover()
    check("워드클라우드 도구 설명", "수치 합" in page.inner_text("#tooltip"), True)
    page.mouse.move(0, 0)
    page.locator("#chart-trend svg").focus()
    page.keyboard.press("ArrowRight")
    check("선그래프 키보드 이동", "2월" in page.inner_text("#tooltip"), True)
    page.locator("#f-reset").focus()

    # 온라인 후기: 기간별 건수를 원본 JSON과 분류 규칙으로 다시 세어 화면과 대조
    spec = importlib.util.spec_from_file_location("build_reviews", os.path.join(HERE, "build_reviews.py"))
    rvmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rvmod)
    rv_rows = rvmod.analyse(rvmod.load_posts())
    raw_links = {r["post"]["link"]: r for r in rv_rows}
    rv_seq = {r["post"]["link"]: i for i, r in enumerate(rv_rows)}
    # 배포 파일에는 근거 글만 남아야 한다
    with open(os.path.join(HERE, "reviews.js"), encoding="utf-8") as fh:
        rv_file = json.loads(fh.read()[len("window.REVIEWS="):].rstrip(";"))
    kept = {p["u"] for p in rv_file["posts"]}
    rel_links = {r["post"]["link"] for r in rv_rows if r["relevant"]}
    check("근거 글이 원본 관련 글 안에 있음", kept <= rel_links, True)
    check("협찬 의심 글이 배포 파일에 없음", any(raw_links[u]["sponsor"] == "suspect" for u in kept), False)
    check("건수와 실제 관련 글 수", rv_file["relevantPosts"], len(rel_links))
    print(f"  [배포 파일] 관련 글 {len(rel_links):,}건 중 근거로 남긴 글 {len(kept):,}건, 나머지 {len(rel_links - kept):,}건은 건수만", flush=True)
    seen_ledes = {}
    for label, lo, hi in [("기본", 0, 31), ("2024", 0, 11), ("2025", 12, 23), ("2026", 24, 31), ("2026-09", 32, 32), ("2026-10", 33, 33), ("전체", 0, 33)]:
        page.click("#f-reset")
        page.select_option("#f-from", str(lo))
        page.select_option("#f-to", str(hi))
        rel = [r for r in rv_rows if r["relevant"] and lo <= rvmod.month_index(r["post"]["date"]) <= hi]
        young = [r for r in rel if r["age"] == "direct"]
        sus = sum(r["sponsor"] == "suspect" for r in rel)
        lede = page.inner_text("#review-lede")
        seen_ledes[label] = lede
        check(f"후기 {label} 관련 글", f"{len(rel):,}건" in lede, True)
        check(f"후기 {label} '20대' 언급", f"'20대' 언급 글 {len(young):,}건" in lede, True)
        check(f"후기 {label} 협찬 의심", f"협찬 의심 {sus:,}건" in lede, True)
        got = page.evaluate("() => __dash.model.reviews.groups")
        for kind, items in got.items():
            pool = rel if kind == "i" else [r for r in rel if r["post"]["groups"] != ["complaint"]]
            for it in items:
                code = f"{kind}:{it['key']}"
                hit = [r for r in pool if code in r["labels"]]
                check(f"후기 {label} {code} 전체", it["total"], len(hit))
                check(f"후기 {label} {code} '20대'", it["young"], sum(r["age"] == "direct" for r in hit))
                usable = sum(r["sponsor"] != "suspect" for r in hit)
                check(f"후기 {label} {code} 근거 수", len(it["evidence"]), min(5, usable))
                # 건수만 남긴 뒤에도 전체 글로 뽑은 상위 5건과 같아야 한다
                ranked = sorted((rvmod.evidence_key(r, rv_seq[r["post"]["link"]], code), r["post"]["link"]) for r in hit if r["sponsor"] != "suspect")
                check(f"후기 {label} {code} 근거 일치", [e["url"] for e in it["evidence"]], [u for _, u in ranked[:5]])
                for e in it["evidence"]:
                    r = raw_links.get(e["url"])
                    check(f"후기 근거가 원본에 있음", r is not None, True)
                    if r:
                        check("후기 근거 협찬 제외", r["sponsor"] != "suspect", True)
                        check("후기 근거 기간 안", lo <= rvmod.month_index(r["post"]["date"]) <= hi, True)
        if label == "전체":
            check("후기 근거 링크 표시", page.locator("#reviews details.rv-item a[target=_blank]").count() >= 3 * 20, True)
    page.click("#f-reset")
    src = page.inner_text("#review-source")
    check("후기 출처 한 줄", src.startswith("네이버 블로그 검색 API의 제목·요약 기준, 수집 기간") and f"총 {len(rv_rows):,}건" in src, True)
    check("'20대 후기' 표현 없음", "20대 후기" in page.inner_text("#reviews"), False)
    check("후기 기간별 표시가 다름", len(set(seen_ledes.values())), len(seen_ledes))
    print("  [후기 기간별 표시]", flush=True)
    for k, v in seen_ledes.items():
        print("   ", k, ":", v, flush=True)

    # 키 노출 검사: 값은 출력하지 않고 파일 이름만 알린다
    env_path = os.path.join(HERE, ".env")
    keys = [l.split("=", 1)[1].strip().strip("'\"") for l in open(env_path, encoding="utf-8-sig") if "=" in l] if os.path.exists(env_path) else []
    leaked = []
    for base, _, names in os.walk(ROOT):
        for n in names:
            if n == ".env" or n.endswith(".xlsx") or n.endswith(".pdf"):
                continue
            with open(os.path.join(base, n), "rb") as fh:
                blob = fh.read()
            if any(k and k.encode() in blob for k in keys):
                leaked.append(n)
    check("키가 다른 파일에 없음", leaked, [])

    # 분석 결과의 고정 문구 수치를 원본에서 따로 계산해 대조
    a20 = defaultdict(int)
    for r in AGE:
        if r["E"] == 20:
            a20[r["A"]] += r["F"]
    rng = lambda a, b: sum(v for k, v in a20.items() if a <= k <= b)
    inb = lambda a, b: sum(r["D"] for r in INB if a <= r["A"] <= b)
    interp, action, chk = page.inner_text("#an-interp"), page.inner_text("#an-action"), page.inner_text("#an-check")
    check("해석: 20대 2026 1~8월", f"{abs((rng(202601, 202608) / rng(202501, 202508) - 1) * 100):.1f}%" in interp, True)
    check("해석: 입도 2026 1~8월", f"+{(inb(202601, 202608) / inb(202501, 202508) - 1) * 100:.1f}%" in interp, True)
    cat_sum = Counter()
    for r in VIS:
        cat_sum[r["B"]] += r["E"]
    check("해석: 관광지 비중", f"{cat_sum['관광지'] / sum(cat_sum.values()) * 100:.1f}%" in interp, True)
    avg = lambda mo: sum(v for k, v in a20.items() if k % 100 == mo) / sum(1 for k in a20 if k % 100 == mo)
    check("해석: 7·8월 평균", f"{round((avg(7) + avg(8)) / 2) / 1e4:.1f}만" in interp, True)
    check("해석: 4월 평균", f"{round(avg(4)) / 1e4:.1f}만" in interp, True)
    check("제안: 2026-04 증감", f"{abs((a20[202604] / a20[202504] - 1) * 100):.1f}%" in action, True)
    check("제안: 2026-05 증감", f"{abs((a20[202605] / a20[202505] - 1) * 100):.1f}%" in action, True)
    mismatch = sum(r["F"] != r["H"] + r["I"] for r in POP)
    check("추가 확인: 도착 불일치 행", f"{mismatch:,}행" in chk, True)
    print("  [분석 문구]\n" + interp + "\n" + chk + "\n" + action, flush=True)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        page.locator("details.tbl summary").first.click()
        page.screenshot(path=os.path.join(SHOTS, "light_1440.png"), full_page=True)
        apply(page, SCENARIOS[5])
        page.screenshot(path=os.path.join(SHOTS, "light_filtered.png"), full_page=True)
        apply(page, SCENARIOS[3])
        page.screenshot(path=os.path.join(SHOTS, "light_empty.png"), full_page=True)
    for w, h, scheme, name in [(390, 844, "light", "phone"), (768, 1000, "light", "tablet"), (1100, 800, "light", "laptop"), (1440, 1000, "dark", "dark")]:
        c2 = br.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
        pg = c2.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(url)
        pg.wait_for_selector("#map svg")
        check(name + " 가로 넘침 없음", pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), True)
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=True)
        c2.close()
    check("브라우저 오류 없음", errors, [])
    br.close()

    # Edge에서도 같은 값이 나오는지 한 조합만 확인
    try:
        edge = p.chromium.launch(channel="msedge")
    except Exception as exc:
        edge = None
        print("  Edge 확인 건너뜀:", exc)
    if edge:
        pg = edge.new_page()
        pg.goto(url)
        pg.wait_for_selector("#map svg")
        apply(pg, SCENARIOS[4])
        ex = expected(SCENARIOS[4])
        check("Edge 20대 합계", fmt(ex["total"]) + "명" in pg.inner_text("#kpi-visitors"), True)
        check("Edge 장소 쪽 표시", f"/ {ex['placeCount']:,}" in pg.inner_text("#place-pager"), True)
        edge.close()

print(f"\n대조 {checks}건, 실패 {len(fails)}건")
for f in fails:
    print("  실패:", f)
sys.exit(1 if fails else 0)
