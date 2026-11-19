#!/usr/bin/env python3
"""Final structured extraction of the source report (verbatim content)."""
import pymupdf, json, re, collections

SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)
BULLET = "\uf0b7"

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
    15: dict(name="Tableau 1", ylo=503, yhi=747, cols=[56.7, 220.6, 345.9, 538.7]),
    17: dict(name="Tableau 2", ylo=425, yhi=576, cols=[56.7, 310.0, 406.0, 538.7]),
    20: dict(name="Tableau 3", ylo=110, yhi=657, cols=[56.7, 153.0, 385.1, 434.5, 479.5, 538.7]),
    22: dict(name="Tableau 4", ylo=146, yhi=382, cols=[56.7, 84.0, 317.0, 538.7]),
    23: dict(name="Tableau 5", ylo=81, yhi=372, cols=[56.7, 198.2, 339.0, 401.5, 464.6, 538.7]),
    24: dict(name="Tableau 6", ylo=81, yhi=401, cols=[56.7, 162.6, 538.7]),
}


def spans_in(pno, ylo, yhi):
    out = []
    for b in doc[pno - 1].get_text("dict", clip=pymupdf.Rect(45, ylo, 555, yhi))["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["text"].strip():
                    out.append(dict(bbox=s["bbox"], text=s["text"]))
    return out


def extract_table(pno, cols, ylo, yhi):
    sp = spans_in(pno, ylo, yhi)
    rules = [y for y in hmap[pno] if ylo - 5 <= y <= yhi + 5]
    if len(rules) >= 4:
        bands = list(zip(rules[:-1], rules[1:]))
    else:
        starts = sorted({round(s["bbox"][1], 0) for s in sp if s["bbox"][0] < cols[1]})
        starts = [y for i, y in enumerate(starts) if i == 0 or y - starts[i - 1] > 6]
        bands = []
        for i, y in enumerate(starts):
            top = y - 8
            bot = starts[i + 1] - 8 if i + 1 < len(starts) else yhi
            bands.append((top, bot))
    grid = [[[] for _ in cols[:-1]] for _ in bands]
    for s in sp:
        cy = (s["bbox"][1] + s["bbox"][3]) / 2
        x0 = s["bbox"][0]
        ri = next((i for i, (a, b) in enumerate(bands) if a - 1 <= cy < b + 1), None)
        ci = next((i for i in range(len(cols) - 1) if cols[i] - 2 <= x0 < cols[i + 1]), None)
        if ri is None:
            ri = 0 if cy < bands[0][0] else len(bands) - 1
        if ci is None:
            ci = min(range(len(cols) - 1), key=lambda i: abs(cols[i] - x0))
        grid[ri][ci].append((round(s["bbox"][1], 1), round(x0, 1), s["text"]))
    return [[" ".join(t for _, _, t in sorted(c)).replace("  ", " ").strip() for c in row] for row in grid]


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markup(l):
    out = []
    for sp in l["spans"]:
        if not sp["text"]:
            continue
        txt = esc(sp["text"])
        if ("Bold" in sp["font"] or "bold" in sp["font"]) and sp["text"].strip():
            out.append("<b>" + txt + "</b>")
        else:
            out.append(txt)
    return "".join(out)


def lines_of(page):
    res = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"])
            if not txt.strip(): continue
            sp = [s for s in l["spans"] if s["text"] != ""]
            res.append(dict(text=txt, html=markup(dict(spans=sp)), x0=l["bbox"][0], x1=l["bbox"][2],
                            y0=l["bbox"][1], y1=l["bbox"][3], spans=sp,
                            size=max(s["size"] for s in sp),
                            bold=all(("Bold" in s["font"] or "bold" in s["font"]) for s in sp),
                            boldfrac=(sum(1 for s in sp if s["text"].strip() and
                                          ("Bold" in s["font"] or "bold" in s["font"]))
                                      / max(1, len([s for s in sp if s["text"].strip()]))),
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
c_lines = [l for l in lines_of(doc[0]) if not is_furniture(l)]
cover = dict(title=" ".join(l["text"].strip() for l in c_lines if l["y0"] < 500),
             date=" ".join(l["text"].strip() for l in c_lines if l["y0"] >= 500))

abbr_rows = []
for pno in (9, 10):
    for r in extract_table(pno, [56.7, 126.0, 538.7], 60, 780):
        if r[0] in ("Sigle", "") or r[0].startswith("Abréviations"): continue
        abbr_rows.append(r)

PAGES = [2, 3, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
cur, prev_y = None, None
for pno in PAGES:
    lines = [l for l in lines_of(doc[pno - 1]) if not is_furniture(l)]
    spec = TABLES.get(pno)
    emitted = False
    cur, prev_y = None, None
    for l in lines:
        t = re.sub(r"\s+", " ", l["text"]).strip()
        th = re.sub(r"\s+", " ", l["html"]).strip()
        if not t: continue
        if spec and not emitted and l["y0"] >= spec["ylo"] - 6:
            cap = next((x["text"].strip() for x in lines
                        if x["italic"] and x["text"].strip().startswith("Tableau")), None)
            blocks.append(dict(t="table", caption=cap,
                               rows=extract_table(pno, spec["cols"], spec["ylo"], spec["yhi"])))
            emitted = True
            cur, prev_y = None, None
        if spec and spec["ylo"] - 6 <= l["y0"] <= spec["yhi"] + 1:
            continue

        kind = "p"
        if l["size"] >= 16.5:
            kind = "h1"
        elif l["boldfrac"] >= 0.8 and re.match(r"^\d+\.\d+\.\d+\.", t):
            kind = "h3"
        elif l["anybold"] and l["size"] >= 12.4 and re.match(r"^\d+\.\d+\.", t):
            kind = "h2"
        elif l["italic"] and re.match(r"^(Tableau|Figure)\s", t):
            kind = "caption"
        elif BULLET in t:
            kind = "li"
        elif l["boldfrac"] >= 0.8 and l["x0"] > 300 and re.search(r"MD, MPH$", t):
            kind = "sig_name"
        elif l["boldfrac"] >= 0.8 and len(t) < 110 and not t.endswith((".", ";", ":")):
            kind = "h4"

        if kind in ("h1", "h2", "h3", "h4", "caption"):
            if (kind == "h4" and blocks and blocks[-1]["t"] == "h4"
                    and prev_y is not None and l["y0"] - prev_y < 16.5):
                blocks[-1]["text"] += " " + t
                blocks[-1]["html"] = blocks[-1].get("html", "") + " " + th
            else:
                blocks.append(dict(t=kind, text=t, html=th))
            cur = None
        elif kind == "sig_name":
            blocks.append(dict(t="sig_name", text=t))
            cur = None
        elif kind == "li":
            txt = t.replace(BULLET, "").strip()
            blocks.append(dict(t="li", text=txt, html=re.sub(BULLET + r"\s*", "", th).strip()))
            cur = None
        else:
            gap = None if prev_y is None else l["y0"] - prev_y
            if (blocks and blocks[-1]["t"] == "li" and l["x0"] > 85
                    and gap is not None and gap < 16.5):
                blocks[-1]["text"] += " " + t
                blocks[-1]["html"] = blocks[-1].get("html", "") + " " + th
                prev_y = l["y0"]
                continue
            if cur is not None and cur["t"] == "p" and gap is not None and gap < 16.0:
                cur["text"] += " " + t
                cur["html"] = cur["html"] + " " + th
            else:
                blocks.append(dict(t="p", text=t, html=th))
                cur = blocks[-1]
        prev_y = l["y0"]
    if spec and not emitted:
        cap = next((x["text"].strip() for x in lines
                    if x["italic"] and x["text"].strip().startswith("Tableau")), None)
        blocks.append(dict(t="table", caption=cap,
                           rows=extract_table(pno, spec["cols"], spec["ylo"], spec["yhi"])))

# merge split numbered headings
out, i = [], 0
while i < len(blocks):
    b = blocks[i]
    if b["t"] in ("h1", "h2") and re.fullmatch(r"([IVX]+|\d+(\.\d+)?)\.", b["text"]) and i + 1 < len(blocks):
        out.append(dict(t=b["t"], text=b["text"] + " " + blocks[i + 1]["text"]))
        i += 2
        continue
    out.append(b)
    i += 1
blocks = out

# abbreviations section before "Résumé exécutif"
idx = next(i for i, b in enumerate(blocks) if b.get("text") == "Résumé exécutif")
blocks.insert(idx, dict(t="table", caption=None, rows=abbr_rows, kind="abbr"))
blocks.insert(idx, dict(t="h1", text="Abréviations et acronymes"))

final = []
for b in blocks:
    if b["t"] == "li" and not b.get("text"):
        continue
    if b["t"] in ("h4", "p") and final and final[-1]["t"] == "sig_name" and len(b["text"]) < 45:
        final.append(dict(t="sig_role", text=b["text"]))
        continue
    if b["t"] == "h4" and re.search(r"MD, MPH", b.get("text", "")) and "Directeur" in b["text"]:
        name, role = b["text"].split("MD, MPH", 1)
        final.append(dict(t="sig_name", text=name.strip() + " MD, MPH"))
        final.append(dict(t="sig_role", text=role.strip()))
        continue
    final.append(b)
blocks = final

for b in blocks:
    if "text" in b:
        b["text"] = re.sub(r"\s+", " ", b["text"]).strip()
    if "html" in b:
        b["html"] = re.sub(r"\s+", " ", b["html"]).strip()
        b["html"] = re.sub(r"<b>\s*</b>", "", b["html"])

json.dump(dict(cover=cover, blocks=blocks), open("work/content.json", "w"), ensure_ascii=False, indent=1)
print("blocks:", len(blocks), collections.Counter(b["t"] for b in blocks))
print("cover:", cover)
for b in blocks:
    if b["t"] == "table":
        print(" table", len(b["rows"]), "x", len(b["rows"][0]), "|", (b.get("caption") or "")[:55])
