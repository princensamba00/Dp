#!/usr/bin/env python3
"""Build the editable DOCX counterpart of the report (Md_ref design system)."""
import json, os, re, sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.style import WD_STYLE_TYPE
import design as D

NAVY = RGBColor(0x13, 0x1D, 0x44)
PALE = RGBColor(0xC2, 0xCF, 0xEA)
BLACK = RGBColor(0, 0, 0)
PALE_HEX = "C2CFEA"
NAVY_HEX = "131D44"
RULE_HEX = "B9C2DA"

BODY_FONT = "Newsreader"
HEAD_FONT = "Glacial Indifference"
SERIF_FONT = "Instrument Serif"


# ------------------------------------------------------------------ helpers
def set_font(run, name, size=None, bold=None, color=None, italic=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


PPR_ORDER = ["w:pStyle", "w:keepNext", "w:keepLines", "w:pageBreakBefore", "w:framePr",
             "w:widowControl", "w:numPr", "w:suppressLineNumbers", "w:pBdr", "w:shd",
             "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
             "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd",
             "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
             "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
             "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr",
             "w:sectPr", "w:pPrChange"]


def ppr_add(pPr, el):
    tag = el.tag
    names = [qn(t) for t in PPR_ORDER]
    idx = names.index(tag)
    for child in list(pPr):
        if child.tag in names and names.index(child.tag) > idx:
            child.addprevious(el)
            return el
    pPr.append(el)
    return el


def tblpr_set(table, width_dxa, indent_dxa=None, borders=True, cellmar=None):
    tblPr = table._tbl.tblPr
    for tag in ("w:tblW", "w:tblInd", "w:tblBorders", "w:tblCellMar", "w:tblLayout"):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(width_dxa))
    w.set(qn("w:type"), "dxa")
    tblPr.append(w)
    if indent_dxa is not None:
        ind = OxmlElement("w:tblInd")
        ind.set(qn("w:w"), str(indent_dxa))
        ind.set(qn("w:type"), "dxa")
        tblPr.append(ind)
    if borders:
        bd = OxmlElement("w:tblBorders")
        for edge, sz, color in (("top", 8, NAVY_HEX), ("left", 0, NAVY_HEX),
                                ("bottom", 8, NAVY_HEX), ("right", 0, NAVY_HEX)):
            el = OxmlElement("w:" + edge)
            el.set(qn("w:val"), "single" if sz else "none")
            el.set(qn("w:sz"), str(sz))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
            bd.append(el)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    if cellmar:
        mar = OxmlElement("w:tblCellMar")
        for tag, val in cellmar.items():
            el = OxmlElement("w:" + tag)
            el.set(qn("w:w"), str(val))
            el.set(qn("w:type"), "dxa")
            mar.append(el)
        tblPr.append(mar)


def shade(element, hex_color):
    pPr = element.get_or_add_pPr() if hasattr(element, "get_or_add_pPr") else element
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def no_hyphen(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:suppressAutoHyphens")):
        pPr.remove(old)
    el = OxmlElement("w:suppressAutoHyphens")
    ppr_add(pPr, el)


def keep_with_next(paragraph, val=True):
    paragraph.paragraph_format.keep_with_next = val


def add_runs(paragraph, html, font, size, color=BLACK, force_bold=False):
    """Add <b>…</b> segments as bold runs."""
    for part in re.split(r"(<b>.*?</b>)", html):
        if not part:
            continue
        bold = part.startswith("<b>") or force_bold
        text = re.sub(r"</?b>", "", part)
        run = paragraph.add_run(text)
        set_font(run, font, size, bold=bold, color=color)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def cant_split(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def field(paragraph, instr, font, size, color):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)
    run2 = paragraph.add_run()
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    run2._r.append(instr_el)
    run3 = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    run3._r.append(sep)
    run4 = paragraph.add_run("1")
    set_font(run4, font, size, color=color)
    run5 = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run5._r.append(end)
    return run4


def page_break(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run._r.append(br)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    return p


def band(section, header=True):
    """Navy band across the page in the header / footer."""
    part = section.header if header else section.footer
    part.is_linked_to_previous = False
    for p in list(part.paragraphs):
        p._p.getparent().remove(p._p)
    tbl = part.add_table(rows=1, cols=1, width=Pt(D.PAGE_W))
    tbl.autofit = False
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblpr_set(tbl, int(D.PAGE_W * 20), indent_dxa=int(-D.MARGIN_L * 20),
              borders=False, cellmar={"top": 30, "left": 0, "bottom": 30, "right": 0})
    cell = tbl.rows[0].cells[0]
    cell.width = Pt(D.PAGE_W)
    shade_cell(cell, NAVY_HEX)
    row = tbl.rows[0]
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:trHeight")
    h.set(qn("w:val"), str(int(D.BAND_H * 20)))
    h.set(qn("w:hRule"), "exact")
    trPr.append(h)
    return cell


# ------------------------------------------------------------------ document
def build(out_path):
    data = json.load(open("work/content.json"))
    cover, blocks = data["cover"], data["blocks"]
    toc = json.load(open("work/toc.json"))
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(D.BODY_SIZE)
    normal.font.color.rgb = BLACK
    rpr = normal.element.get_or_add_rPr()
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), BODY_FONT)
    for old in rpr.findall(qn("w:rFonts")):
        rpr.remove(old)
    rpr.insert(0, rf)
    pf = normal.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.space_after = Pt(D.BODY_AFTER)
    pf.space_before = Pt(0)
    pf.line_spacing = Pt(D.BODY_LEAD)

    def mkstyle(name, font, size, bold=False, color=BLACK, before=0, after=0,
                align=WD_ALIGN_PARAGRAPH.LEFT, indent=0, keep=False, leading=None,
                outline=None):
        st = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = doc.styles["Normal"]
        st.font.name = font
        st.font.size = Pt(size)
        st.font.bold = bold
        st.font.color.rgb = color
        srpr = st.element.get_or_add_rPr()
        r = OxmlElement("w:rFonts")
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            r.set(qn(a), font)
        for old in srpr.findall(qn("w:rFonts")):
            srpr.remove(old)
        srpr.insert(0, r)
        p = st.element.get_or_add_pPr()
        f = st.paragraph_format
        f.space_before = Pt(before)
        f.space_after = Pt(after)
        f.alignment = align
        if indent:
            f.left_indent = Pt(indent)
        if leading:
            f.line_spacing = Pt(leading)
        f.keep_with_next = keep
        if outline is not None:
            ol = OxmlElement("w:outlineLvl")
            ol.set(qn("w:val"), str(outline))
            ppr_add(p, ol)
        return st

    mkstyle("H1 ICHESS", HEAD_FONT, 14, bold=True, before=0, after=9.6,
            align=WD_ALIGN_PARAGRAPH.CENTER, keep=True, leading=18, outline=0)
    mkstyle("H2 ICHESS", HEAD_FONT, 12, bold=True, color=NAVY, before=14, after=6,
            keep=True, leading=15, outline=1)
    mkstyle("H3 ICHESS", HEAD_FONT, 10.2, bold=True, before=11, after=4,
            keep=True, leading=13, outline=2)
    mkstyle("H4 ICHESS", BODY_FONT, 11.5, bold=True, color=NAVY, before=9, after=3,
            keep=True, leading=14)
    mkstyle("Corps ICHESS", BODY_FONT, 11.5, after=7.4, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
            leading=14.3)
    mkstyle("Liste ICHESS", BODY_FONT, 11.5, after=4, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
            indent=18, leading=14.4)
    mkstyle("Legende ICHESS", BODY_FONT, 9.3, before=11, after=4, keep=True,
            leading=12, color=NAVY)
    mkstyle("Signature ICHESS", BODY_FONT, 11.5, bold=True, before=16, after=1,
            align=WD_ALIGN_PARAGRAPH.RIGHT, leading=14)
    mkstyle("Signature role", BODY_FONT, 10.5, align=WD_ALIGN_PARAGRAPH.RIGHT, leading=13)

    # ---- section 1: cover
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Pt(D.PAGE_W), Pt(D.PAGE_H)
    sec.left_margin = sec.right_margin = Pt(D.MARGIN_L)
    sec.top_margin = Pt(46 + 36)
    sec.bottom_margin = Pt(84)
    sec.header_distance = Pt(0)
    sec.footer_distance = Pt(0)
    band(sec, header=True)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing = Pt(12)
    p.paragraph_format.tab_stops.add_tab_stop(Emu(int(D.CONTENT_W * 12700)),
                                              WD_TAB_ALIGNMENT.RIGHT)
    r = p.add_run("I C H E S S ,   L L C")
    set_font(r, HEAD_FONT, 10, color=BLACK)
    r = p.add_run("\tF H I  3 6 0  ·  E p i C  R D C")
    set_font(r, HEAD_FONT, 10, color=BLACK)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = Pt(196)

    title_p = doc.add_paragraph()
    title_p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(0)
    title_p.paragraph_format.line_spacing = Pt(31)
    r = title_p.add_run(cover["title"])
    set_font(r, HEAD_FONT, 23, color=BLACK)

    foot = doc.add_paragraph()
    foot.paragraph_format.space_before = Pt(212)
    foot.paragraph_format.space_after = Pt(0)
    foot.paragraph_format.line_spacing = Pt(12)
    foot.paragraph_format.tab_stops.add_tab_stop(Emu(int(D.CONTENT_W * 12700)),
                                                 WD_TAB_ALIGNMENT.RIGHT)
    r = foot.add_run(cover["date"].upper())
    set_font(r, HEAD_FONT, 10, color=BLACK)
    r = foot.add_run("\tRAPPORT FINAL")
    set_font(r, HEAD_FONT, 10, color=BLACK)
    pPr = foot._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "8")
    top.set(qn("w:space"), "10")
    top.set(qn("w:color"), NAVY_HEX)
    pbdr.append(top)
    ppr_add(pPr, pbdr)

    # ---- section 2: body
    new = doc.add_section(WD_SECTION.NEW_PAGE)
    new.page_width, new.page_height = Pt(D.PAGE_W), Pt(D.PAGE_H)
    new.left_margin = new.right_margin = Pt(D.MARGIN_L)
    new.top_margin = Pt(52.6)
    new.bottom_margin = Pt(72)
    new.header_distance = Pt(0)
    new.footer_distance = Pt(0)
    sectPr = new._sectPr
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), "2")
    order = ["footnotePr", "endnotePr", "type", "pgSz", "pgMar", "paperSrc", "pgBorders",
             "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote",
             "titlePg", "textDirection", "bidi", "rtlGutter", "docGrid"]
    idx = order.index("pgNumType")
    for c in list(sectPr):
        tag = c.tag.split("}")[-1]
        if tag in order and order.index(tag) > idx:
            c.addprevious(pg)
            break
    else:
        sectPr.append(pg)

    cell = band(new, header=True)
    cp = cell.paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_before = Pt(0)
    cp.paragraph_format.space_after = Pt(0)
    cp.paragraph_format.line_spacing = Pt(14)
    r = cp.add_run(D.HEADER_1)
    set_font(r, SERIF_FONT, 11, color=PALE)
    cp2 = cell.add_paragraph()
    cp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp2.paragraph_format.space_before = Pt(0)
    cp2.paragraph_format.space_after = Pt(0)
    cp2.paragraph_format.line_spacing = Pt(11)
    r = cp2.add_run(D.HEADER_2)
    set_font(r, BODY_FONT, 8.5, color=PALE)
    fcell = band(new, header=False)
    fp = fcell.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(6)
    fp.paragraph_format.space_after = Pt(0)
    field(fp, " PAGE ", BODY_FONT, 10, PALE)

    first_h1 = True
    toc_done = False
    for b in blocks:
        t = b["t"]
        html = b.get("html", b.get("text", ""))
        if t == "h1":
            if not first_h1:
                page_break(doc)
            first_h1 = False
            if b["text"] == "Résumé exécutif" and not toc_done:
                h = doc.add_paragraph(style="H1 ICHESS")
                r = h.add_run("Table des matières")
                set_font(r, HEAD_FONT, 14, bold=True, color=BLACK)
                no_hyphen(h)
                add_toc(doc, toc)
                page_break(doc)
                toc_done = True
            h = doc.add_paragraph(style="H1 ICHESS")
            r = h.add_run(b["text"])
            set_font(r, HEAD_FONT, 14, bold=True, color=BLACK)
            no_hyphen(h)
        elif t == "h2":
            p = doc.add_paragraph(style="H2 ICHESS")
            add_runs(p, html, HEAD_FONT, 12, NAVY, force_bold=True)
            no_hyphen(p)
        elif t == "h3":
            p = doc.add_paragraph(style="H3 ICHESS")
            add_runs(p, html, HEAD_FONT, 10.2, BLACK, force_bold=True)
            no_hyphen(p)
        elif t == "h4":
            p = doc.add_paragraph(style="H4 ICHESS")
            add_runs(p, html, BODY_FONT, 11.5, NAVY)
            no_hyphen(p)
        elif t == "p":
            p = doc.add_paragraph(style="Corps ICHESS")
            add_runs(p, html, BODY_FONT, 11.5)
            no_hyphen(p)
        elif t == "li":
            p = doc.add_paragraph(style="Liste ICHESS")
            p.paragraph_format.tab_stops.add_tab_stop(Pt(15))
            r = p.add_run("•\t")
            set_font(r, BODY_FONT, 11.5)
            add_runs(p, html, BODY_FONT, 11.5)
            no_hyphen(p)
        elif t == "caption":
            p = doc.add_paragraph(style="Legende ICHESS")
            r = p.add_run(b["text"])
            set_font(r, BODY_FONT, 9.3, italic=True, color=NAVY)
            no_hyphen(p)
        elif t == "sig_name":
            p = doc.add_paragraph(style="Signature ICHESS")
            add_runs(p, html, BODY_FONT, 11.5, force_bold=True)
        elif t == "sig_role":
            p = doc.add_paragraph(style="Signature role")
            add_runs(p, html, BODY_FONT, 10.5)
        elif t == "table":
            add_table(doc, b)

    cp = doc.core_properties
    cp.title = cover["title"]
    cp.author = "ICHESS, LLC"
    cp.subject = "Diagnostic opérationnel rapide de la préparation des établissements de santé"
    cp.language = "fr-FR"
    doc.save(out_path)
    print("saved", out_path)


INNER_W = D.CONTENT_W


def add_table(doc, b):
    rows = b["rows"]
    if b.get("kind") == "abbr":
        hdr = ["Sigle", "Signification"]
        widths = [92, INNER_W - 92]
        first_bold = True
        body_size, body_lead = 9.8, 12.2
    else:
        name = (b.get("caption") or "").split(":")[0]
        widths = {
            "Tableau 1": [152, 138, 176.88],
            "Tableau 2": [150, 160, 156.88],
            "Tableau 3": [98, 158, 60, 56, 94.88],
            "Tableau 4": [26, 236, 204.88],
            "Tableau 5": [126, 118, 58, 60, 104.88],
            "Tableau 6": [104, 362.88],
        }.get(name, [INNER_W / len(rows[0])] * len(rows[0]))
        hdr = rows[0]
        rows = rows[1:]
        first_bold = False
        body_size, body_lead = 9.0, 11.2
    table = doc.add_table(rows=1 + len(rows), cols=len(widths))
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tblpr_set(table, int(sum(widths) * 20), borders=True,
              cellmar={"top": 64, "left": 100, "bottom": 64, "right": 100})
    for i, width in enumerate(widths):
        for cell in table.columns[i].cells:
            cell.width = Pt(width)
    for i, txt in enumerate(hdr):
        cell = table.rows[0].cells[i]
        shade_cell(cell, NAVY_HEX)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = Pt(10.6)
        r = p.add_run(txt)
        set_font(r, BODY_FONT, 8.8, bold=True, color=PALE)
    repeat_header(table.rows[0])
    cant_split(table.rows[0])
    for ri, row in enumerate(rows, start=1):
        cant_split(table.rows[ri])
        for ci, val in enumerate(row):
            cell = table.rows[ri].cells[ci]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(body_lead)
            r = p.add_run(val)
            set_font(r, BODY_FONT, body_size, bold=(first_bold and ci == 0), color=BLACK)
            no_hyphen(p)
    after = doc.add_paragraph()
    after.paragraph_format.space_before = Pt(0)
    after.paragraph_format.space_after = Pt(0)
    after.paragraph_format.line_spacing = Pt(12)


def add_toc(doc, entries):
    first = True
    last_p = None
    for e in entries:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(4.5 if e["level"] == 0 else 0)
        pf.space_after = Pt(0)
        pf.line_spacing = Pt(15.8 if e["level"] == 0 else (14.8 if e["level"] == 1 else 14.0))
        pf.left_indent = Pt(0 if e["level"] == 0 else (18 if e["level"] == 1 else 34))
        pf.tab_stops.add_tab_stop(Emu(int(D.CONTENT_W * 12700)), WD_TAB_ALIGNMENT.RIGHT,
                                  WD_TAB_LEADER.DOTS)
        if first:
            run = p.add_run()
            fb = OxmlElement("w:fldChar")
            fb.set(qn("w:fldCharType"), "begin")
            run._r.append(fb)
            run2 = p.add_run()
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = r' TOC \o "1-3" \h \z \u '
            run2._r.append(it)
            run3 = p.add_run()
            sep = OxmlElement("w:fldChar")
            sep.set(qn("w:fldCharType"), "separate")
            run3._r.append(sep)
            first = False
        size = 11.0 if e["level"] == 0 else (11.2 if e["level"] == 1 else 10.4)
        r = p.add_run(e["text"])
        set_font(r, BODY_FONT, size, bold=(e["level"] == 0), color=BLACK)
        r = p.add_run("\t" + str(e["page"]))
        set_font(r, BODY_FONT, 10.2, bold=(e["level"] == 0), color=NAVY)
        no_hyphen(p)
        last_p = p
    end = last_p.add_run()
    fe = OxmlElement("w:fldChar")
    fe.set(qn("w:fldCharType"), "end")
    end._r.append(fe)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "work/out/report.docx"
    build(out)
