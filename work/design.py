"""Shared design tokens measured from Md_ref.pdf (the design model)."""
import os

NAVY = "#131D44"          # bandeaux, en-têtes de tableaux
PALE = "#C2CFEA"          # texte des bandeaux / en-têtes de tableaux
YELLOW = "#FFDE59"        # accent du modèle
LBLUE = "#8DA1FF"         # accent secondaire du modèle
BLACK = "#000000"
GREY = "#6B7280"

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONTS = {
    "body": "Newsreader-Regular-Full.ttf",
    "body-bold": "Newsreader-Bold-Full.ttf",
    "body-italic": "Newsreader-Italic-Full.ttf",
    "head": "GlacialIndifference-Regular.ttf",
    "head-bold": "GlacialIndifference-Bold.ttf",
    "serif": "InstrumentSerif-Regular.ttf",
}

# geometry (points, A4)
PAGE_W, PAGE_H = 595.28, 841.89
MARGIN_L = MARGIN_R = 64.2
BAND_H = 46.0                 # bandeaux haut et bas
CONTENT_TOP = PAGE_H - 52.6   # haut du bloc de texte (comme Md_ref)
CONTENT_BOTTOM = BAND_H + 26  # limite basse du bloc de texte
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

HEADER_1 = "ICHESS, LLC"
HEADER_2 = "International Center for Health Systems Strengthening"

# typography
BODY_SIZE, BODY_LEAD = 11.5, 14.4
BODY_AFTER = 7.6
