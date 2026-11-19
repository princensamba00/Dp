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


def add_runs(paragraph, html, font, size, color=BLACK):
    """Add <b>…</b> segments as bold runs."""
    for part in re.split(r"(<b>.*?</b>)", html):
        if not part:
            continue
        bold = part.startswith("<b>")
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
