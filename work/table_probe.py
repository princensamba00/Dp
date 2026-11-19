#!/usr/bin/env python3
"""Extract tables from the source PDF using border rules + text positions."""
import pymupdf, json, sys, collections

SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)

# --- global rule statistics to drop page-furniture lines
vcount = collections.Counter()
hcount = collections.Counter()
vmap, hmap = {}, {}
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
    vmap[pno] = sorted(vs); hmap[pno] = sorted(hs)
    for x in vs: vcount[x] += 1
    for y in hs: hcount[y] += 1

def table_grid(pno, ylo, yhi):
    p = doc[pno - 1]
    vs = [x for x in vmap[pno] if 40 < x < 560 and vcount[x] <= 2 and ylo - 20 < 800]
    # keep vertical rules that actually intersect the table's vertical span
    keep = []
    for x in vs:
        for dr in p.get_drawings():
            for it in dr["items"]:
                r = it[1] if it[0] in ("re", "qu") else None
                if it[0] == "l":
                    a, b = it[1], it[2]
                    if abs(a.x - b.x) < 0.6 and abs(a.x - x) < 0.8:
                        if not (b.y < ylo or a.y > yhi): keep.append(x)
                elif r is not None and r.width < 1.2:
                    if abs(r.x0 - x) < 0.8 and not (r.y1 < ylo or r.y0 > yhi): keep.append(x)
    cols = sorted(set(keep))
    rows = [y for y in hmap[pno] if ylo - 3 <= y <= yhi + 3]
    return cols, rows

def lines_in(pno, ylo, yhi):
    p = doc[pno - 1]
    out = []
    for b in p.get_text("dict", clip=pymupdf.Rect(40, ylo, 560, yhi))["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                out.append((l["bbox"], t, any("Bold" in s["font"] for s in l["spans"])))
    return out

TABLES = {
    15: dict(ylo=505, yhi=750, name="Tableau 1"),
    17: dict(ylo=425, yhi=578, name="Tableau 2"),
    20: dict(ylo=112, yhi=660, name="Tableau 3"),
    22: dict(ylo=148, yhi=384, name="Tableau 4"),
    23: dict(ylo=83, yhi=374, name="Tableau 5"),
    24: dict(ylo=83, yhi=403, name="Tableau 6"),
}

if __name__ == "__main__":
    for pno, spec in TABLES.items():
        cols, rows = table_grid(pno, spec["ylo"], spec["yhi"])
        print(f"=== p{pno} {spec['name']} cols={cols} rows={rows}")
