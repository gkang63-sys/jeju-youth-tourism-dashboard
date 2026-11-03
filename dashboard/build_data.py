"""원본 엑셀을 읽어 대시보드가 쓰는 data.js를 만든다. 표준 라이브러리만 사용한다.

원칙: 값을 바꾸거나 행을 지우지 않는다. 같은 키의 행은 합계와 행 수만 묶는다.
사용법: python build_data.py
"""
import base64, json, os, posixpath, re, struct, sys, zipfile
import xml.etree.ElementTree as ET
from array import array
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def col_index(ref):
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def read_sheet(name, sheet=None):
    with zipfile.ZipFile(os.path.join(ROOT, name)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as fh:
                for _, el in ET.iterparse(fh):
                    if el.tag == M + "si":
                        shared.append("".join(t.text or "" for t in el.iter(M + "t")))
                        el.clear()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall(PR + "Relationship")}
        target = next(targets[s.get(R + "id")] for s in wb.find(M + "sheets") if sheet is None or s.get("name") == sheet)
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        rows = []
        with z.open(path) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag != M + "row":
                    continue
                vals = {}
                for c in el.findall(M + "c"):
                    t, v = c.get("t"), c.find(M + "v")
                    i = col_index(c.get("r"))
                    if t == "inlineStr":
                        vals[i] = "".join(x.text or "" for x in c.iter(M + "t"))
                    elif v is None or v.text is None:
                        continue
                    elif t == "s":
                        vals[i] = shared[int(v.text)]
                    elif t == "str":
                        vals[i] = v.text
                    else:
                        n = float(v.text)
                        vals[i] = int(n) if n.is_integer() else n
                el.clear()
                rows.append([vals.get(i) for i in range(max(vals) + 1)] if vals else [])
    return rows


def b64(typecode, values):
    arr = array(typecode, values)
    if sys.byteorder != "little":
        arr.byteswap()
    return base64.b64encode(arr.tobytes()).decode("ascii")


def expect_header(rows, *names):
    for want, got in zip(names, rows[0]):
        if want != got:
            raise SystemExit(f"열 이름이 다릅니다: {want!r} / {got!r}")
    return rows[1:]


def month_index(ym):
    return (ym // 100 - 2024) * 12 + ym % 100 - 1


def main():
    # 1) 입도 관광객
    inbound = expect_header(read_sheet("월별 입도 관광객.xlsx"), "기준연월", "내국인 입도 관광객수", "외국인 입도 관광객수", "전체 입도 관광객수")
    # 2) 연령대
    age = expect_header(read_sheet("제주 연령대별 방문.xlsx"), "기준연월", "시도코드", "시도명", "성별", "연령", "방문객수")
    # 3) 읍면동
    emd = expect_header(read_sheet("제주 지역별 방문객(읍면동).xlsx", "제주 지역별 방문객(읍면동)"), "기준연월", "읍면동코드", "시도명", "시군구명", "읍면동명", "내국인 방문객수", "외국인 방문객수", "총 방문객수 (내국인+외국인)", "주민센터 주소")
    emd_info = {}
    for r in emd:
        emd_info[r[4]] = (r[1], r[3])
    emd_names = sorted(emd_info, key=lambda n: emd_info[n][0])
    emd_idx = {n: i for i, n in enumerate(emd_names)}

    # 4) 비짓제주: 주소 글자에서 시군구와 읍면동을 찾을 수 있을 때만 표시한다
    search = expect_header(read_sheet("비짓제주 검색어 순위.xlsx"), "기준년월", "분류명", "지역명", "주소", "수치")
    eup_myeon = [n for n in emd_names if n[-1] in "읍면"]
    dong = {n for n in emd_names if n[-1] == "동"}

    def locate(addr):
        hit = next((n for n in eup_myeon if n in addr), None)
        if hit is None:
            hit = next((t for t in addr.split() if t in dong), None)
        if "서귀포시" in addr:
            sgg = 1
        elif "제주시" in addr:
            sgg = 0
        elif hit is not None:
            sgg = 0 if emd_info[hit][1] == "제주시" else 1
        else:
            sgg = 2  # 주소로 확인 불가
        return sgg, emd_idx[hit] if hit is not None else 255

    s_cats = sorted({r[1] for r in search})
    s_names, s_addrs = {}, {}
    s_groups = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in search:
        n = s_names.setdefault(str(r[2]), len(s_names))
        a = s_addrs.setdefault(r[3], len(s_addrs))
        g = s_groups[(s_cats.index(r[1]), n, a)][month_index(r[0])]
        g[0] += r[4]
        g[1] += 1
    a_loc = {a: locate(a) for a in s_addrs}
    addr_by_id = {i: a for a, i in s_addrs.items()}
    s_key_cat, s_key_name, s_key_addr, s_key_sgg, s_key_emd, s_off, s_mon, s_sum, s_cnt = [], [], [], [], [], [0], [], [], []
    for (c, n, a), months in s_groups.items():
        sgg, e = a_loc[addr_by_id[a]]
        s_key_cat.append(c); s_key_name.append(n); s_key_addr.append(a); s_key_sgg.append(sgg); s_key_emd.append(e)
        for m in sorted(months):
            s_mon.append(m); s_sum.append(months[m][0]); s_cnt.append(months[m][1])
        s_off.append(len(s_mon))

    # 5) 인기 장소
    pop = expect_header(read_sheet("제주 지역별 인기 장소.xlsx"), "주행일자(YYYYMM)", "목적지명", "목적지주소", "읍면동코드", "읍면동명", "도착건수", "카테고리 3단계", "관광객 도착 수", "도민 도착 수")
    p_names, p_addrs, p_cats = {}, {}, {}
    p_groups = defaultdict(list)
    for r in pop:
        n = p_names.setdefault(str(r[1]), len(p_names))
        a = p_addrs.setdefault(r[2], len(p_addrs))
        c = p_cats.setdefault(r[6], len(p_cats))
        p_groups[(n, a, emd_idx[r[4]], c)].append((month_index(r[0]), r[5], r[7], r[8]))
    p_key_name, p_key_addr, p_key_emd, p_key_cat, p_off, p_mon, p_arr, p_tour, p_res = [], [], [], [], [0], [], [], [], []
    for (n, a, e, c), rows in p_groups.items():
        p_key_name.append(n); p_key_addr.append(a); p_key_emd.append(e); p_key_cat.append(c)
        for m, x, t, d in sorted(rows):
            p_mon.append(m); p_arr.append(x); p_tour.append(t); p_res.append(d)
        p_off.append(len(p_mon))
    if max(p_arr + p_tour + p_res) > 65535 or max(s_sum) > 65535:
        raise SystemExit("16비트 범위를 넘는 값이 있습니다")

    # 6) 경계: 코드 10자리로 연결하고, 8자리 코드와 이름이 함께 맞는지 확인한다
    with open(os.path.join(HERE, "jeju_boundary.json"), encoding="utf-8") as fh:
        boundary = json.load(fh)
    pop_code = {r[4]: r[3] for r in pop}
    geo = {}
    for f in boundary["features"]:
        match = next((n for n in emd_names if str(emd_info[n][0]) == f["code10"]), None)
        if match is None or match != f["name"] or str(pop_code[match]) != f["code8"]:
            raise SystemExit(f"경계와 코드가 맞지 않습니다: {f['name']} {f['code10']} {f['code8']}")
        geo[match] = f["rings"]
    if len(geo) != len(emd_names):
        raise SystemExit("경계에 없는 읍면동이 있습니다")

    data = {
        "base": 202401,
        "boundarySource": boundary["source"],
        "inbound": [[month_index(r[0]), r[1], r[2], r[3]] for r in inbound],
        "age": [[month_index(r[0]), r[3], r[4], r[5]] for r in age],
        "emd": {
            "names": emd_names,
            "sgg": [emd_info[n][1] for n in emd_names],
            "code10": [emd_info[n][0] for n in emd_names],
            "code8": [pop_code[n] for n in emd_names],
            "rows": [[month_index(r[0]), emd_idx[r[4]], r[5], r[6], r[7]] for r in emd],
            "geo": [geo[n] for n in emd_names],
        },
        "search": {
            "cats": s_cats,
            "names": list(s_names),
            "addrs": list(s_addrs),
            "rows": len(search),
            "keyCat": b64("B", s_key_cat), "keyName": b64("I", s_key_name), "keyAddr": b64("I", s_key_addr),
            "keySgg": b64("B", s_key_sgg), "keyEmd": b64("B", s_key_emd),
            "off": b64("I", s_off), "mon": b64("B", s_mon), "sum": b64("H", s_sum), "cnt": b64("B", s_cnt),
        },
        "pop": {
            "names": list(p_names),
            "addrs": list(p_addrs),
            "cats": list(p_cats),
            "rows": len(pop),
            "keyName": b64("I", p_key_name), "keyAddr": b64("I", p_key_addr),
            "keyEmd": b64("B", p_key_emd), "keyCat": b64("H", p_key_cat),
            "off": b64("I", p_off), "mon": b64("B", p_mon), "arr": b64("H", p_arr), "tour": b64("H", p_tour), "res": b64("H", p_res),
        },
    }
    out = os.path.join(HERE, "data.js")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("window.DATA=")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";")
    print("data.js", round(os.path.getsize(out) / 1048576, 1), "MB")
    print("검색 묶음", len(s_key_cat), "월값", len(s_mon), "원본 행", len(search), "행 수 합", sum(s_cnt))
    print("장소 묶음", len(p_key_name), "월값", len(p_mon), "원본 행", len(pop))


if __name__ == "__main__":
    main()
