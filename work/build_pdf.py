#!/usr/bin/env python3
"""Render the report to PDF reproducing the Md_ref (design model) visual system."""
import json, os, re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily, stringWidth
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, KeepTogether, Flowable,
                                NextPageTemplate, CondPageBreak)
import design as D

F = D.FONT_DIR
for name, key in [("Body", "body"), ("Body-Bold", "body-bold"), ("Body-Italic", "body-italic"),
                  ("Head", "head"), ("Head-Bold", "head-bold"), ("Serif", "serif")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(F, D.FONTS[key])))
registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                   boldItalic="Body-Bold")
registerFontFamily("Head", normal="Head", bold="Head-Bold", italic="Head", boldItalic="Head-Bold")

NAVY = colors.HexColor(D.NAVY)
PALE = colors.HexColor(D.PALE)
RULE = colors.HexColor("#B9C2DA")
BLACK = colors.black

S = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=D.BODY_SIZE, leading=D.BODY_LEAD - 0.1,
                           alignment=TA_JUSTIFY, spaceAfter=D.BODY_AFTER - 0.2, textColor=BLACK, allowWidows=0,
                           splitLongWords=0, embeddedHyphenation=0),
    "li": ParagraphStyle("li", fontName="Body", fontSize=D.BODY_SIZE, leading=D.BODY_LEAD,
                         alignment=TA_JUSTIFY, leftIndent=18, bulletIndent=2,
                         spaceBefore=1, spaceAfter=4, bulletFontName="Body",
                         bulletFontSize=D.BODY_SIZE, embeddedHyphenation=0),
    "h1": ParagraphStyle("h1", fontName="Head-Bold", fontSize=14, leading=18,
                         alignment=TA_CENTER, textColor=BLACK, spaceBefore=0, spaceAfter=9.6),
    "h2": ParagraphStyle("h2", fontName="Head-Bold", fontSize=12, leading=15,
                         textColor=NAVY, spaceBefore=14, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Head-Bold", fontSize=10.2, leading=13,
                         textColor=BLACK, spaceBefore=11, spaceAfter=4),
    "h4": ParagraphStyle("h4", fontName="Body-Bold", fontSize=11.5, leading=14,
                         textColor=NAVY, spaceBefore=9, spaceAfter=3),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=9.3, leading=12,
                              textColor=NAVY, spaceBefore=11, spaceAfter=4),
    "sig_name": ParagraphStyle("sig", fontName="Body-Bold", fontSize=11.5, leading=14,
                               alignment=TA_RIGHT, spaceBefore=16, spaceAfter=1),
    "sig_role": ParagraphStyle("sigr", fontName="Body", fontSize=10.5, leading=13,
                               alignment=TA_RIGHT, spaceAfter=0),
}
TBL_HDR = ParagraphStyle("th", fontName="Body-Bold", fontSize=8.8, leading=10.6, textColor=PALE)
TBL_TXT = ParagraphStyle("td", fontName="Body", fontSize=9.0, leading=11.2, textColor=BLACK)
TBL_TXT_C = ParagraphStyle("tdc", parent=TBL_TXT, alignment=TA_CENTER)
TBL_K = ParagraphStyle("tdk", fontName="Body-Bold", fontSize=9.0, leading=11.2, textColor=BLACK)
TBL_ABBR_K = ParagraphStyle("abk", fontName="Body-Bold", fontSize=9.8, leading=12.2, textColor=BLACK)
TBL_ABBR_V = ParagraphStyle("abv", fontName="Body", fontSize=9.8, leading=12.2, textColor=BLACK)
TBL_ABBR_H = ParagraphStyle("abh", fontName="Body-Bold", fontSize=10.4, leading=13, textColor=PALE)

CONTENT_W = D.CONTENT_W

COVER = BLOCKS = TITLE = SUBJECT = None


class H(Paragraph):
    def __init__(self, text_html, level, style):
        Paragraph.__init__(self, text_html, S[style])
        self._toc_level = level
        self._toc_text = re.sub(r"<[^>]+>", "", text_html).strip()


def build_table(rows, widths, header_rows=1, cell_rules=None, center_cols=(),
                hdr_style=TBL_HDR, txt_style=TBL_TXT):
    data = []
    for ri, row in enumerate(rows):
        out = []
        for ci, cell in enumerate(row):
            if ri < header_rows:
                out.append(Paragraph(cell, hdr_style))
            elif cell_rules and (ri, ci) in cell_rules:
                out.append(Paragraph(cell, cell_rules[(ri, ci)]))
            elif ci in center_cols:
                out.append(Paragraph(cell, TBL_TXT_C))
            else:
                out.append(Paragraph(cell, txt_style))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=header_rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.9),
        ("TOPPADDING", (0, 0), (-1, header_rows - 1), 5.2),
        ("BOTTOMPADDING", (0, 0), (-1, header_rows - 1), 5.2),
        ("LINEBELOW", (0, header_rows), (-1, -2), 0.25, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, NAVY),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, NAVY),
        ("LINEBELOW", (0, header_rows - 1), (-1, header_rows - 1), 0.8, NAVY),
    ]))
    return t


class Report(BaseDocTemplate):
    def __init__(self, path):
        BaseDocTemplate.__init__(self, path, pagesize=A4,
                                 leftMargin=D.MARGIN_L, rightMargin=D.MARGIN_R,
                                 topMargin=D.PAGE_H - D.CONTENT_TOP,
                                 bottomMargin=D.CONTENT_BOTTOM,
                                 title=TITLE, author="ICHESS, LLC", subject=SUBJECT,
                                 creator="ICHESS, LLC", keywords="préparation opérationnelle; ESS; RDC")
        frame = Frame(D.MARGIN_L, D.CONTENT_BOTTOM, CONTENT_W,
                      D.CONTENT_TOP - D.CONTENT_BOTTOM, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=self.cover_page),
                               PageTemplate(id="body", frames=[frame], onPage=self.body_page)])
        self.records = []

    def body_page(self, canv, doc):
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, D.PAGE_H - D.BAND_H, D.PAGE_W, D.BAND_H, stroke=0, fill=1)
        canv.rect(0, 0, D.PAGE_W, D.BAND_H, stroke=0, fill=1)
        canv.setFillColor(PALE)
        canv.setFont("Serif", 11)
        canv.drawCentredString(D.PAGE_W / 2, D.PAGE_H - 22.5, D.HEADER_1)
        canv.setFont("Body", 8.5)
        canv.drawCentredString(D.PAGE_W / 2, D.PAGE_H - 40.0, D.HEADER_2)
        canv.setFont("Body", 10)
        canv.drawCentredString(D.PAGE_W / 2, 24.3, str(doc.page))
        canv.restoreState()

    def cover_page(self, canv, doc):
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, D.PAGE_H - D.BAND_H, D.PAGE_W, D.BAND_H, stroke=0, fill=1)
        canv.rect(0, 0, D.PAGE_W, D.BAND_H, stroke=0, fill=1)
        canv.setFillColor(BLACK)
        tracked(canv, "ICHESS, LLC", D.MARGIN_L, D.PAGE_H - 82, "Head", 10, 2.2)
        rt = "FHI 360 · EpiC RDC"
        w = tracked_width(rt, "Head", 10, 2.2)
        tracked(canv, rt, D.PAGE_W - D.MARGIN_R - w, D.PAGE_H - 82, "Head", 10, 2.2)
        words, lines, cur = COVER["title"].split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if stringWidth(t, "Head", 24) <= CONTENT_W:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        leading = 31
        total = len(lines) * leading
        y = D.PAGE_H * 0.575 + total / 2
        canv.setFont("Head", 24)
        for ln in lines:
            canv.drawCentredString(D.PAGE_W / 2, y - leading + 5, ln)
            y -= leading
        canv.setStrokeColor(NAVY)
        canv.setLineWidth(0.8)
        canv.line(D.MARGIN_L, 84, D.PAGE_W - D.MARGIN_R, 84)
        canv.setFillColor(BLACK)
        tracked(canv, COVER["date"].upper(), D.MARGIN_L, 66, "Head", 10, 2.2)
        rt = "RAPPORT FINAL"
        w = tracked_width(rt, "Head", 10, 2.2)
        tracked(canv, rt, D.PAGE_W - D.MARGIN_R - w, 66, "Head", 10, 2.2)
        canv.restoreState()

    def afterFlowable(self, flowable):
        if hasattr(flowable, "_toc_level"):
            key = "h%d-%d" % (flowable._toc_level, len(self.records))
            try:
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(flowable._toc_text, key,
                                          level=flowable._toc_level, closed=False)
            except Exception:
                pass
            self.records.append([flowable._toc_level, flowable._toc_text, self.page])


def tracked(canv, text, x, y, font, size, tracking):
    canv.setFont(font, size)
    for ch in text:
        canv.drawString(x, y, ch)
        x += stringWidth(ch, font, size) + tracking


def tracked_width(text, font, size, tracking):
    return sum(stringWidth(c, font, size) + tracking for c in text) - tracking


class TOC(Flowable):
    def __init__(self, entries, width):
        Flowable.__init__(self)
        self.entries = list(entries)
        self.width = width
        self.spec = {0: (11.0, 15.8, 0, "Body-Bold", 4.5),
                     1: (11.2, 14.8, 18, "Body", 0),
                     2: (10.4, 14.0, 34, "Body", 0)}
        self.height = sum(self.spec[e[0]][1] + self.spec[e[0]][4] for e in self.entries) + 4

    def wrap(self, aw, ah):
        return self.width, self.height

    def split(self, aw, ah):
        if ah >= self.height:
            return [self]
        acc, head, tail, first = 0, [], [], True
        for e in self.entries:
            step = self.spec[e[0]][1] + self.spec[e[0]][4]
            if first or acc + step <= ah:
                head.append(e)
                acc += step
                first = False
            else:
                tail.append(e)
        if not tail:
            return []
        return [TOC(head, self.width), TOC(tail, self.width)]

    def draw(self):
        c = self.canv
        y = self.height
        for level, text, page in self.entries:
            size, lead, indent, font, before = self.spec[level]
            y -= before + lead
            base = y + (lead - size) / 2 + 1.6
            c.setFillColor(BLACK)
            c.setFont(font, size)
            c.drawString(indent, base, text)
            tw = stringWidth(text, font, size)
            num = str(page)
            c.setFont("Body-Bold" if level == 0 else "Body", 10.2)
            nw = stringWidth(num, "Body-Bold" if level == 0 else "Body", 10.2)
            start, end = indent + tw + 7, self.width - nw - 6
            if end > start:
                c.setFont("Body", 8.6)
                c.setFillColor(NAVY)
                dotw = stringWidth(".", "Body", 8.6) + 3.1
                n = max(0, int((end - start) / dotw))
                x = start
                for _ in range(n):
                    c.drawString(x, base + 0.9, ".")
                    x += dotw
            c.setFillColor(NAVY if level == 0 else BLACK)
            c.setFont("Body-Bold" if level == 0 else "Body", 10.2)
            c.drawRightString(self.width, base, num)


def table_flow(b):
    rows = b["rows"]
    if b.get("kind") == "abbr":
        rows = [["Sigle", "Signification"]] + rows
        rules = {(i, 0): TBL_ABBR_K for i in range(1, len(rows))}
        return build_table(rows, [92, CONTENT_W - 92], cell_rules=rules,
                           hdr_style=TBL_ABBR_H,
                           txt_style=TBL_ABBR_V)
    name = (b.get("caption") or "").split(":")[0]
    widths = {
        "Tableau 1": [152, 138, 176.88],
        "Tableau 2": [150, 160, 156.88],
        "Tableau 3": [98, 158, 60, 56, 94.88],
        "Tableau 4": [26, 236, 204.88],
        "Tableau 5": [126, 118, 58, 60, 104.88],
        "Tableau 6": [104, 362.88],
    }.get(name, [CONTENT_W / len(rows[0])] * len(rows[0]))
    center = (2,) if name == "Tableau 5" else ()
    t = build_table(rows, widths, center_cols=center)
    t.spaceBefore = 2
    t.spaceAfter = 12
    return t


def make_story(toc_entries):
    story = [Spacer(1, D.PAGE_H * 0.75), NextPageTemplate("body"), PageBreak()]
    inserted_toc = False
    first_h1 = True
    lvl_map = {"h2": 1, "h3": 2}
    blocks = BLOCKS
    n = len(blocks)
    i = 0
    while i < n:
        b = blocks[i]
        t = b["t"]
        if t in ("h2", "h3", "h4"):
            group = [b]
            j = i + 1
            while j < n and blocks[j]["t"] in ("h3", "h4") and t != "h4":
                group.append(blocks[j])
                j += 1
            flows = []
            for g in group:
                gt = g["t"]
                if gt == "h4":
                    flows.append(Paragraph(g.get("html", g["text"]), S["h4"]))
                else:
                    flows.append(H(g.get("html", g["text"]), lvl_map[gt], gt))
            story.append(CondPageBreak(100 if len(flows) > 1 else 74))
            story.append(KeepTogether(flows) if len(flows) > 1 else flows[0])
            i = j
            continue
        if t == "h1":
            text = b.get("html", b["text"])
            if not first_h1:
                story.append(PageBreak())
            first_h1 = False
            if b["text"] == "Résumé exécutif" and not inserted_toc:
                story.append(H("Table des matières", 0, "h1"))
                story.append(TOC(toc_entries, CONTENT_W))
                story.append(PageBreak())
                inserted_toc = True
                story.append(H(text, 0, "h1"))
            else:
                story.append(H(text, 0, "h1"))
        elif t == "p":
            story.append(Paragraph(b.get("html", b["text"]), S["body"]))
        elif t == "li":
            story.append(Paragraph(b.get("html", b["text"]), S["li"], bulletText="•"))
        elif t == "caption":
            story.append(CondPageBreak(96))
            story.append(Paragraph(b.get("html", b["text"]), S["caption"]))
        elif t == "sig_name":
            story.append(Paragraph(b.get("html", b["text"]), S["sig_name"]))
        elif t == "sig_role":
            story.append(Paragraph(b.get("html", b["text"]), S["sig_role"]))
        elif t == "table":
            flow = table_flow(b)
            if len(b["rows"]) > 8:
                story.append(CondPageBreak(170))
            story.append(flow)
        i += 1
    return story


def build(path, toc_entries):
    doc = Report(path)
    doc.build(make_story(toc_entries))
    return [tuple(r) for r in doc.records]


if __name__ == "__main__":
    data = json.load(open("work/content.json"))
    COVER, BLOCKS = data["cover"], data["blocks"]
    TITLE = COVER["title"]
    SUBJECT = "Diagnostic opérationnel rapide de la préparation des établissements de santé"
    out = sys.argv[1] if len(sys.argv) > 1 else "work/out/report.pdf"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    entries = []
    for it in range(4):
        recs = build(out, entries)
        new = [r for r in recs if r[1] != "Table des matières"]
        if new == entries:
            break
        entries = new
    print("pages:", len(__import__("pymupdf").open(out)), "| toc entries:", len(entries))
    json.dump([{"level": l, "text": t, "page": p} for l, t, p in entries],
              open("work/toc.json", "w"), ensure_ascii=False, indent=1)
