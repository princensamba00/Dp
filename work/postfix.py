#!/usr/bin/env python3
"""Merge page-break continuation paragraphs and check content fidelity."""
import json, re, pymupdf, difflib, sys

d = json.load(open("work/content.json"))
bs = d["blocks"]

out = []
for b in bs:
    if b["t"] == "p" and b["text"][:1].islower() and any(x["t"] == "p" for x in out):
        # locate the previous paragraph
        j = len(out) - 1
        while j >= 0 and out[j]["t"] not in ("p",):
            j -= 1
        if j >= 0:
            out[j]["text"] = out[j]["text"].rstrip() + " " + b["text"]
            if "html" in out[j]:
                out[j]["html"] = out[j]["html"].rstrip() + " " + b.get("html", b["text"])
            continue
    out.append(b)
d["blocks"] = out
json.dump(d, open("work/content.json", "w"), ensure_ascii=False, indent=1)
print("blocks after merge:", len(out))

# ---------------------------------------------------------------- fidelity
SRC = "Rapport_Diagnostic_Operationnel_Rapide_ESS_EpiC_RDC_FHI360_ICHESS_Rapport_final_version_propre_05-11-26.pdf"
doc = pymupdf.open(SRC)
PAGES = [2, 3, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
src_chunks = []
for pno in PAGES:
    page = doc[pno - 1]
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0: continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"])
            if l["bbox"][1] < 56 and ("ICHESS" in t or "International" in t): continue
            if l["bbox"][1] > 780 and re.fullmatch(r"\s*\d+\s*", t): continue
            src_chunks.append(t)
src = " ".join(src_chunks)
src = src.replace("\uf0b7", " ")
src = re.sub(r"\s+", " ", src)

model_chunks = []
for b in d["blocks"]:
    if b["t"] == "table":
        for r in b["rows"]:
            model_chunks.extend(r)
    else:
        model_chunks.append(b["text"])
model = re.sub(r"\s+", " ", " ".join(model_chunks))

sw, mw = src.split(), model.split()
print("src words:", len(sw), "model words:", len(mw))
sm = difflib.SequenceMatcher(None, sw, mw, autojunk=False)
print("similarity:", round(sm.ratio(), 5))
gaps = [op for op in sm.get_opcodes() if op[0] != "equal"]
print("diff blocks:", len(gaps))
for tag, i1, i2, j1, j2 in gaps[:40]:
    print(f"  {tag}: SRC[{' '.join(sw[i1:i2])[:90]!r}] -> MODEL[{' '.join(mw[j1:j2])[:90]!r}]")
