#!/usr/bin/env python3
"""Extract the six main tables of the source PDF into a JSON structure."""
import pymupdf, json, collections

SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)

vcount, hcount, vmap, hmap = collections.Counter(), collections.Counter(), {}, {}
for pno, p in enumerate(doc, 1):
    vs, hs = set(), set()
    for dr in p.get_drawings():
        for it in dr["items"]:
            if it[0] == "re":
                r = it[1]
                if r.width < 1.2 and r.height > 5: vs.add(round(r.x0, 1))
                if r.height < 1.2 and r.width > 5: hs.add(round(r.y0, 1))
            elif it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.x - b.x) < 0.6 and abs(a.y - b.y) > 5: vs.add(round(a.x, 1))
                if abs(a.y - b.y) < 0.6 and abs(a.x - b.x) > 5: hs.add(round(a.y, 1))
    vmap[pno], hmap[pno] = sorted(vs), sorted(hs)
    for x in vs: vcount[x] += 1
    for y in hs: hcount[y] += 1

TABLES = {
    15: dict(ylo=505, yhi=750, name="Tableau 1", ncols=3),
    17: dict(ylo=425, yhi=578, name="Tableau 2", ncols=3),
    20: dict(ylo=112, yhi=660, name="Tableau 3", ncols=5),
    22: dict(ylo=148, yhi=384, name="Tableau 4", ncols=3),
    23: dict(ylo=83, yhi=374, name="Tableau 5", ncols=5),
    24: dict(ylo=83, yhi=403, name="Tableau 6", ncols=2),
}

def lines_in(pno, ylo, yhi):
    p = doc[pno - 1]
    out = []
    for b in p.get_text("dict", clip=pymupdf.Rect(45, ylo, 555, yhi))["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                out.append(dict(bbox=l["bbox"], text=t,
                                bold=any("Bold" in s["font"] for s in l["spans"])))
    return out

def extract(pno, spec):
    ylo, yhi = spec["ylo"], spec["yhi"]
    ls = lines_in(pno, ylo, yhi)
    inner = [x for x in vmap[pno] if vcount[x] <= 2 and 56 < x < 539]
    cols = [56.7] + inner + [538.7]
    if not inner:  # derive from text
        xs = sorted({round(l["bbox"][0], 0) for l in ls})
        groups = []
        for x in xs:
            if groups and x - groups[-1][-1] <= 6: groups[-1].append(x)
            else: groups.append([x])
        cuts = [sum(g) / len(g) for g in groups]
        cols = [56.7] + [c - 4 for c in cuts[1:]] + [538.7]
    rows = [y for y in hmap[pno] if ylo - 3 <= y <= yhi + 3]
    if len(rows) < 4:  # derive rows from text baselines
        ys = []
        for l in sorted(ls, key=lambda l: l["bbox"][1]):
            if not ys or l["bbox"][1] - ys[-1] > 8: ys.append(l["bbox"][1])
        rows = [ys[0] - 6] + [y - 5 for y in ys[1:]] + [yhi]
    grid = [[[] for _ in cols[:-1]] for _ in rows[:-1]]
    for l in ls:
        cy = (l["bbox"][1] + l["bbox"][3]) / 2
        cx = (l["bbox"][0] + l["bbox"][2]) / 2
        ri = next((i for i in range(len(rows) - 1) if rows[i] <= cy < rows[i + 1]), None)
        ci = next((i for i in range(len(cols) - 1) if cols[i] <= l["bbox"][0] + 2 < cols[i + 1]), None)
        if ri is None or ci is None:
            print("  !! unplaced", pno, l["text"][:40])
            continue
        grid[ri][ci].append((l["bbox"][1], l["text"]))
    out = []
    for r in grid:
        out.append([" ".join(t for _, t in sorted(c)) for c in r])
    return out, cols, rows

if __name__ == "__main__":
    res = {}
    for pno, spec in TABLES.items():
        g, cols, rows = extract(pno, spec)
        res[spec["name"]] = {"page": pno, "rows": g, "cols": [round(c, 1) for c in cols]}
        print(f"===== {spec['name']} (p{pno}) {len(g)}x{len(g[0])} cols={[round(c,1) for c in cols]}")
        for r in g:
            print("  | " + " || ".join(x[:48] for x in r))
    json.dump(res, open("work/tables.json", "w"), ensure_ascii=False, indent=1)
