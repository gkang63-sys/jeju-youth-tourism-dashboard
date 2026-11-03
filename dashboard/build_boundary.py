"""행정동 경계 GeoJSON에서 제주 43개 읍면동만 골라 단순화해 jeju_boundary.json으로 저장한다.

사용법: python build_boundary.py <HangJeongDong_ver20261001.geojson 경로>
결과 파일이 이미 폴더에 있으므로 경계 자료를 바꿀 때만 다시 실행하면 된다.
"""
import json, math, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
TOLERANCE = 0.0007   # 도 단위, 약 70m
MIN_AREA = 2e-6      # 이보다 작은 부속 섬은 생략 (읍면동마다 가장 큰 고리는 항상 유지)


def simplify(pts, tol):
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = 0, None
        for i in range(a + 1, b):
            d = abs(dy * (pts[i][0] - ax) - dx * (pts[i][1] - ay)) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(ring):
    return abs(sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring)))) / 2


def main(path):
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    out = []
    for f in gj["features"]:
        p = f["properties"]
        if p.get("sido") != "50":
            continue
        rings = []
        polys = f["geometry"]["coordinates"]
        if f["geometry"]["type"] == "Polygon":
            polys = [polys]
        for poly in polys:
            rings.append([tuple(c[:2]) for c in poly[0]])  # 바깥 고리만 사용
        largest = max(area(r) for r in rings)
        kept = []
        for r in rings:
            if area(r) < MIN_AREA and area(r) < largest:
                continue
            # 닫힌 고리는 시작점과 끝점이 같아 한 번에 단순화하면 전부 지워지므로 둘로 나눈다
            mid = len(r) // 2
            s = simplify(r[: mid + 1], TOLERANCE)[:-1] + simplify(r[mid:], TOLERANCE)
            if len(s) >= 4:
                kept.append([[round(x, 5), round(y, 5)] for x, y in s])
        out.append({"name": p["adm_nm"].split()[-1], "sgg": p["sggnm"], "code10": p["adm_cd2"], "code8": p["adm_cd"], "rings": kept})
    out.sort(key=lambda r: r["code10"])
    print("읍면동", len(out), "점", sum(len(r) for o in out for r in o["rings"]))
    with open(os.path.join(HERE, "jeju_boundary.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": gj.get("name"), "features": out}, fh, ensure_ascii=False, separators=(",", ":"))


main(sys.argv[1])
