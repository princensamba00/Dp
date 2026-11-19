#!/usr/bin/env python3
"""Build the structured content model of the source report (verbatim text)."""
import pymupdf, json, re, collections

SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)
BULLET = "\uf0b7"

# ---------------------------------------------------------------- rule stats
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
    15: dict(name="Tableau 1", ylo=505, yhi=750, cols=[56.7, 220.6, 345.9, 538.7]),
    17: dict(name="Tableau 2", ylo=425, yhi=578, cols=[56.7, 310.0, 406.0, 538.7]),
    20: dict(name="Tableau 3", ylo=112, yhi=660, cols=[56.7, 153.0, 385.1, 434.5, 479.5, 538.7]),
    22: dict(name="Tableau 4", ylo=148, yhi=384, cols=[56.7, 84.0, 317.0, 538.7]),
    23: dict(name="Tableau 5", ylo=83, yhi=374, cols=[56.7, 198.2, 339.0, 401.5, 464.6, 538.7]),
    24: dict(name="Tableau 6", ylo=83, yhi=403, cols=[56.7, 162.6, 538.7]),
}


def spans_in(pno, ylo, yhi):
    p = doc[pno - 1]
    out = []
    for b in p.get_text("dict", clip=pymupdf.Rect(45, ylo, 555, yhi))["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["text"].strip():
                    out.append(dict(bbox=s["bbox"], text=s["text"],
                                    bold=("Bold" in s["font"] or "bold" in s["font"])))
    return out


def extract_table(pno, spec):
    sp = spans_in(pno, spec["ylo"], spec["yhi"])
    cols, rows_rules = spec["cols"], [y for y in hmap[pno] if spec["ylo"] - 4 <= y <= spec["yhi"] + 4]
    if len(rows_rules) < 4:                      # rows from leading numbers/text
        first = sorted({round(s["bbox"][1], 0) for s in sp if s["bbox"][0] < cols[1]})
        starts, seen = [], set()
        for y in first:
            if y not in seen:
                starts.append(y); seen.add(y)
        starts = [y for i, y in enumerate(starts)
                  if i == 0 or y - starts[i - 1] > 6]
        bands = [(y - 4.5, y + 7) for y in starts]
    else:
        bands = list(zip(rows_rules[:-1], rows_rules[1:]))
    grid = [[[] for _ in cols[:-1]] for _ in bands]
    for s in sp:
        cy, x0, x1 = (s["bbox"][1] + s["bbox"][3]) / 2, s["bbox"][0], s["bbox"][2]
        ri = next((i for i, (a, b) in enumerate(bands) if a - 1 <= cy < b + 1), None)
        ci = next((i for i in range(len(cols) - 1) if cols[i] - 2 <= x0 < cols[i + 1]), None)
        if ri is None:
            ri = min(range(len(bands)), key=lambda i: abs((bands[i][0] + bands[i][1]) / 2 - cy))
        if ci is None:
            ci = min(range(len(cols) - 1), key=lambda i: abs(cols[i] - x0))
        grid[ri][ci].append((round(s["bbox"][1], 1), round(s["bbox"][0], 1), s["text"]))
    out = []
    for row in grid:
        out.append([" ".join(t for _, _, t in
                             sorted(c, key=lambda v: (v[0], v[1]))).strip() for c in row])
    return out


# ---------------------------------------------------------------- page lines
def lines_of(page):
    res = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"])
            if not txt.strip(): continue
            sp = [s for s in l["spans"] if s["text"].strip()]
            res.append(dict(text=txt, x0=l["bbox"][0], y0=l["bbox"][1], y1=l["bbox"][3],
                            size=max(s["size"] for s in sp),
                            bold=all(("Bold" in s["font"] or "bold" in s["font"]) for s in sp),
                            anybold=any(("Bold" in s["font"] or "bold" in s["font"]) for s in sp),
                            italic=any("Italic" in s["font"] for s in sp)))
    res.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
    return res


def is_furniture(l):
    t = l["text"].strip()
    if l["y0"] < 56 and ("ICHESS" in t or "International Center" in t): return True
    if l["y0"] > 780 and re.fullmatch(r"\d+", t): return True
    return False


blocks, cover = [], None
SKIP_PAGES = []            # pages fully consumed as source TOC / lists

for pno, page in enumerate(doc, 1):
    lines = [l for l in lines_of(page) if not is_furniture(l)]
    if pno == 1:
        cover = dict(title=" ".join(l["text"].strip() for l in lines if l["y0"] < 500),
                     date=" ".join(l["text"].strip() for l in lines if l["y0"] >= 500))
        continue
    if pno in TABLES:
        cap = next((l["text"].strip() for l in lines if l["italic"] and l["text"].strip().startswith("Tableau")), None)
        rows = extract_table(pno, TABLES[pno])
        blocks.append(dict(t="table", caption=cap, rows=rows, name=TABLES[pno]["name"]))
        ylo, yhi = TABLES[pno]["ylo"], TABLES[pno]["yhi"]
        lines = [l for l in lines if not (ylo - 6 <= l["y0"] <= yhi + 2)]
        cur = None
    cur = None
    prev_y = None
    for l in lines:
        t = re.sub(r"\s+", " ", l["text"]).strip()
        if not t: continue
        kind = "p"
        if l["size"] >= 16.5:
            kind = "h1"
        elif l["bold"] and re.match(r"^\d+\.\d+\.\d+\.", t):
            kind = "h3"
        elif (l["bold"] or l["anybold"]) and l["size"] >= 12.4 and re.match(r"^\d+\.\d+\.", t):
            kind = "h2"
        elif l["italic"] and re.match(r"^(Tableau|Figure)\s", t):
            kind = "caption"
        elif t.startswith(BULLET):
            kind = "li"
        elif l["bold"] and l["size"] <= 12 and len(t) < 90 and not t.endswith((".", ";", ":", "»")):
            kind = "h4"
        elif t.endswith(("MD, MPH", "PhD, MD, MPH")) and l["x0"] > 300:
            kind = "sig_name"

        if kind in ("h1", "h2", "h3", "h4", "caption", "sig_name"):
            blocks.append(dict(t=kind, text=t))
            cur = None
        elif kind == "li":
            txt = t.replace(BULLET, "").strip()
            if blocks and blocks[-1]["t"] == "li" and prev_y is not None and l["y0"] - prev_y < 16.5:
                blocks[-1]["text"] += " " + txt
            else:
                blocks.append(dict(t="li", text=txt))
                cur = blocks[-1]
            cur = None
        else:
            gap = None if prev_y is None else l["y0"] - prev_y
            if cur is not None and cur["t"] == "p" and gap is not None and gap < 16.0:
                cur["text"] += " " + t
            else:
                blocks.append(dict(t="p", text=t))
                cur = blocks[-1]
        prev_y = l["y0"]

# ---------------------------------------------------------------- fix-ups
fixed = []
for b in blocks:
    if b["t"] in ("h1", "h2") and re.fullmatch(r"([IVX]+|\d+(\.\d+)?)\.", b.get("text", "")):
        b["_pending"] = True
    fixed.append(b)

merged = []
i = 0
while i < len(fixed):
    b = fixed[i]
    if b.get("_pending") and i + 1 < len(fixed):
        nxt = fixed[i + 1]
        b = dict(t=b["t"], text=b["text"] + " " + nxt["text"])
        i += 1
    merged.append(b)
    i += 1
blocks = merged

for b in blocks:
    if "text" in b:
        b["text"] = re.sub(r"\s+", " ", b["text"]).strip()
        if b["t"] == "sig_name":
            b["text"] = b["text"].replace(" PhD, MD, MPH", " PhD, MD, MPH")

json.dump(dict(cover=cover, blocks=blocks), open("work/content.json", "w"),
          ensure_ascii=False, indent=1)
print("blocks:", len(blocks), collections.Counter(b["t"] for b in blocks))
for b in blocks:
    if b["t"] == "table":
        print(b["name"], len(b["rows"]), "x", len(b["rows"][0]), "|", b["caption"])
