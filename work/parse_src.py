#!/usr/bin/env python3
"""Parse the source PDF into a structured content model (verbatim text)."""
import pymupdf, json, re

SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)

def get_lines(page, clip=None):
    out = []
    for b in page.get_text("dict", clip=clip)["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"])
            if not txt.strip():
                continue
            fonts = [(s["font"], round(s["size"], 1)) for s in l["spans"] if s["text"].strip()]
            out.append({
                "text": txt,
                "x0": l["bbox"][0], "y0": l["bbox"][1], "x1": l["bbox"][2], "y1": l["bbox"][3],
                "fonts": fonts,
                "size": max((f[1] for f in fonts), default=11),
                "bold": any("Bold" in f[0] or "bold" in f[0] for f in fonts),
                "italic": any("Italic" in f[0] for f in fonts),
            })
    out.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
    return out

def is_running(l):
    t = l["text"].strip()
    if l["y0"] < 56 and ("ICHESS" in t or "International Center" in t):
        return True
    if l["y0"] > 780 and re.fullmatch(r"\d+", t):
        return True
    return False

def cluster_cols(x0s, tol=6):
    xs = sorted(x0s)
    groups = []
    for x in xs:
        if groups and x - groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [sum(g) / len(g) for g in groups]

def extract_table(page, bbox):
    clip = pymupdf.Rect(bbox)
    lines = get_lines(page, clip=clip)
    if not lines:
        return []
    cols = cluster_cols([l["x0"] for l in lines])
    rows = []
    for l in lines:
        if rows and l["y0"] <= rows[-1]["y1"] + 0.5:
            rows[-1]["lines"].append(l)
            rows[-1]["y1"] = max(rows[-1]["y1"], l["y1"])
        else:
            rows.append({"lines": [l], "y1": l["y1"]})
    grid = []
    for r in rows:
        cells = {}
        for l in r["lines"]:
            ci = min(range(len(cols)), key=lambda i: abs(cols[i] - l["x0"]))
            cells.setdefault(ci, []).append(l["text"].strip())
        grid.append([(" ".join(cells.get(i, [])).strip()) for i in range(len(cols))])
    return grid

blocks = []
cover = None
table_boxes = {}

for pno, page in enumerate(doc, start=1):
    lines = [l for l in get_lines(page) if not is_running(l)]
    # tables on this page
    tabs = []
    for t in page.find_tables().tables:
        b = t.bbox
        tabs.append(b)
    table_boxes[pno] = tabs

    if pno == 1:
        cover = {"title": " ".join(l["text"].strip() for l in lines if l["y0"] < 500),
                 "date": " ".join(l["text"].strip() for l in lines if l["y0"] >= 500)}
        continue

    inside = lambda l: any(b[0] - 2 <= l["x0"] and l["y0"] >= b[1] - 2 and l["y1"] <= b[3] + 2 for b in tabs)

    cur = None
    prev_y = None
    for l in lines:
        if inside(l):
            cur = None
            continue
        t = l["text"].strip()
        if any(b[1] - 2 <= l["y0"] and l["y1"] <= b[3] + 2 for b in tabs):
            cur = None
            continue
        # classification
        kind = None
        if l["size"] >= 17 and re.match(r"^(I{1,3}V?|IV|V)\.", t):
            kind = "h1"
        elif l["size"] >= 17:
            kind = "h1"
        elif l["bold"] and re.match(r"^\d+\.\d+\.\d+\.", t):
            kind = "h3"
        elif l["bold"] and l["size"] >= 12.5 and re.match(r"^\d+\.\d+\.", t):
            kind = "h2"
        elif l["italic"] and re.match(r"^(Tableau|Figure)\s", t):
            kind = "caption"
        elif "\uf0b7" in t or l["x0"] > 85:
            kind = "li"
        else:
            kind = "p"

        if kind in ("h1", "h2", "h3", "caption"):
            blocks.append({"t": kind, "text": t})
            cur = None
        elif kind == "li":
            txt = t.replace("\uf0b7", "").strip()
            if blocks and blocks[-1]["t"] == "li" and prev_y is not None and l["y0"] - prev_y < 16.5:
                blocks[-1]["text"] += " " + txt
            else:
                blocks.append({"t": "li", "text": txt})
            cur = blocks[-1]
        else:
            gap = None if prev_y is None else l["y0"] - prev_y
            if cur is not None and cur["t"] == "p" and gap is not None and gap < 16.0:
                cur["text"] += " " + t
            else:
                blocks.append({"t": "p", "text": t})
                cur = blocks[-1]
        prev_y = l["y0"]

    for b in tabs:
        # caption just before table
        cap = None
        if blocks and blocks[-1]["t"] == "caption":
            cap = blocks.pop()["text"]
        rows = extract_table(page, b)
        blocks.append({"t": "table", "caption": cap, "rows": rows, "src_page": pno})

# cleanup
for b in blocks:
    if "text" in b:
        b["text"] = re.sub(r"\s+", " ", b["text"]).strip()

json.dump({"cover": cover, "blocks": blocks}, open("work/content.json", "w"),
          ensure_ascii=False, indent=1)

with open("work/outline.txt", "w") as f:
    for b in blocks:
        if b["t"] == "table":
            f.write(f"[TABLE p{b['src_page']}] caption={b['caption']} rows={len(b['rows'])} cols={max(len(r) for r in b['rows'])}\n")
        else:
            f.write(f"[{b['t']}] {b['text'][:110]}\n")
print("blocks:", len(blocks))
print(cover)
