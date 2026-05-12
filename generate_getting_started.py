"""
Generates mushroom_tracker_getting_started.pdf in the same directory.
Run: python generate_getting_started.py
"""

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Frame, PageTemplate, NextPageTemplate
from reportlab.platypus.flowables import Flowable
from pathlib import Path
from datetime import date

OUTPUT = Path(__file__).parent / "mushroom_tracker_getting_started.pdf"
W, H = A4

# ── Palette ───────────────────────────────────────────────────────────────────
GREEN        = HexColor("#2d6a4f")
GREEN_LIGHT  = HexColor("#52b788")
GREEN_BG     = HexColor("#d8f3dc")
AMBER        = HexColor("#b5890a")
AMBER_BG     = HexColor("#fff3cd")
AMBER_BORDER = HexColor("#f0c040")
BLUE         = HexColor("#1a5276")
BLUE_BG      = HexColor("#dbeafe")
BLUE_BORDER  = HexColor("#93c5fd")
TAN          = HexColor("#c4a87a")
STEP_BG      = HexColor("#0c0a08")
STEP_GREEN   = HexColor("#74c27a")
GRAY_DARK    = HexColor("#333333")
GRAY_MID     = HexColor("#666666")
GRAY_LIGHT   = HexColor("#f5f5f5")
GRAY_RULE    = HexColor("#dddddd")
WHITE        = HexColor("#ffffff")
TABLE_ALT    = HexColor("#f9f9f9")
CODE_BG      = HexColor("#f0f4f0")
CODE_BORDER  = HexColor("#c8e6c9")
COVER_BG     = HexColor("#0c0a08")
COVER_GREEN  = HexColor("#74c27a")
LOGO_PATH    = Path(__file__).parent / "logo.png.png"

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def ms(name, parent_name="Normal", **kw):
    return ParagraphStyle(name=name, parent=base[parent_name], **kw)

TITLE   = ms("TITLE",   fontSize=22, textColor=GREEN, fontName="Helvetica-Bold",
             leading=28, spaceAfter=6, spaceBefore=16)
H2      = ms("H2",      fontSize=13, textColor=GREEN, fontName="Helvetica-Bold",
             leading=17, spaceAfter=5, spaceBefore=12)
H3      = ms("H3",      fontSize=11, textColor=GRAY_DARK, fontName="Helvetica-Bold",
             leading=14, spaceAfter=4, spaceBefore=8)
BODY    = ms("BODY",    fontSize=10, textColor=GRAY_DARK, fontName="Helvetica",
             leading=15, spaceAfter=5, spaceBefore=2)
BODY_SM = ms("BODY_SM", fontSize=9,  textColor=GRAY_MID, fontName="Helvetica",
             leading=13, spaceAfter=3)
BULLET  = ms("BULLET",  fontSize=10, textColor=GRAY_DARK, fontName="Helvetica",
             leading=15, spaceAfter=3, leftIndent=14)
CODE_S  = ms("CODE_S",  fontSize=9,  textColor=HexColor("#1e4d2b"), fontName="Courier",
             leading=13, spaceAfter=2)
STEP_LBL = ms("STEP_LBL", fontSize=28, textColor=STEP_GREEN, fontName="Helvetica-Bold",
              leading=32)
STEP_TITLE = ms("STEP_TITLE", fontSize=16, textColor=WHITE, fontName="Helvetica-Bold",
                leading=20, spaceAfter=4)


def p(text, style=BODY):     return Paragraph(text, style)
def sp(n=6):                 return Spacer(1, n)
def rule():                  return HRFlowable(width="100%", thickness=0.5,
                                               color=GRAY_RULE, spaceAfter=6, spaceBefore=4)

def bullet(items):
    return [Paragraph(f"&#8226; &nbsp; {item}", BULLET) for item in items]

def action(items):
    """Numbered action list."""
    out = []
    for i, item in enumerate(items, 1):
        s = ms(f"_act{i}", fontSize=10, textColor=GRAY_DARK, fontName="Helvetica",
               leading=15, spaceAfter=4, leftIndent=22, firstLineIndent=-22)
        out.append(Paragraph(f"<b>{i}.</b> &nbsp; {item}", s))
    return out

def callout(text, color=GREEN_BG, border=GREEN_LIGHT, label=None):
    content = f"<b>{label}</b>  {text}" if label else text
    inner = Paragraph(content, ms("_cb", fontSize=9, textColor=GRAY_DARK, leading=14))
    t = Table([[inner]], colWidths=[W - 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), color),
        ("BOX",          (0,0), (-1,-1), 0.75, border),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
    ]))
    return t

def field_table(rows):
    """Two-column table: field name | what to enter."""
    hdr = [Paragraph("<b>Field</b>", ms("_fh", fontSize=9, textColor=WHITE,
                                         fontName="Helvetica-Bold", leading=12)),
           Paragraph("<b>What to enter</b>", ms("_fh2", fontSize=9, textColor=WHITE,
                                                  fontName="Helvetica-Bold", leading=12))]
    body = []
    for name, desc in rows:
        body.append([
            Paragraph(name, ms("_fn", fontSize=9, textColor=GRAY_DARK, fontName="Helvetica-Bold", leading=13)),
            Paragraph(desc, ms("_fd", fontSize=9, textColor=GRAY_DARK, fontName="Helvetica", leading=13)),
        ])
    t = Table([hdr] + body, colWidths=[4.5*cm, W - 4*cm - 4.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), GREEN),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, TABLE_ALT]),
        ("LINEBELOW",      (0,1), (-1,-1), 0.3, GRAY_RULE),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
    ]))
    return t

def step_header(number, title, subtitle=""):
    """Dark header bar with large step number."""
    num_cell  = Paragraph(str(number), STEP_LBL)
    title_cell = Table(
        [[Paragraph(title, STEP_TITLE)],
         [Paragraph(subtitle, ms("_ss", fontSize=10, textColor=HexColor("#8b949e"),
                                  fontName="Helvetica", leading=14))]] if subtitle else
        [[Paragraph(title, STEP_TITLE)]],
        colWidths=[W - 4*cm - 2.5*cm]
    )
    title_cell.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2),
    ]))
    outer = Table([[num_cell, title_cell]], colWidths=[2.5*cm, W - 4*cm - 2.5*cm])
    outer.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), STEP_BG),
        ("LEFTPADDING",  (0,0), (0,0), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW",    (0,0), (-1,-1), 2, STEP_GREEN),
    ]))
    return outer


# ── Page canvas ───────────────────────────────────────────────────────────────

class NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        pg = self._pageNumber
        if pg <= 1:
            return
        self.setFont("Helvetica", 8)
        self.setFillColor(GRAY_MID)
        self.drawRightString(W - 2*cm, 1.4*cm, f"Page {pg - 1} of {total - 1}")
        self.drawString(2*cm, 1.4*cm, "Mushroom Tracker -- Getting Started Guide")
        self.setStrokeColor(GRAY_RULE)
        self.setLineWidth(0.3)
        self.line(2*cm, 1.8*cm, W - 2*cm, 1.8*cm)


# ── Mushroom drawing helper ───────────────────────────────────────────────────

def _draw_mushroom(c, cx, cy, cap_rw, cap_rh, cap_color, stem_color):
    """Draw a toadstool. (cx, cy) is base of cap / top of stem."""
    stem_w = cap_rw * 0.42
    stem_h = cap_rh * 1.1
    c.setFillColor(stem_color)
    c.roundRect(cx - stem_w, cy - stem_h, stem_w * 2, stem_h + 2,
                stem_w * 0.7, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#5a4030"))
    c.setLineWidth(0.8)
    path = c.beginPath()
    path.moveTo(cx - cap_rw * 0.75, cy)
    path.curveTo(cx - cap_rw * 0.4, cy + cap_rh * 0.35,
                 cx + cap_rw * 0.4, cy + cap_rh * 0.35,
                 cx + cap_rw * 0.75, cy)
    c.drawPath(path, fill=0, stroke=1)
    c.setLineWidth(1)
    c.setFillColor(cap_color)
    dome = c.beginPath()
    dome.arc(cx - cap_rw, cy - cap_rh, cx + cap_rw, cy + cap_rh,
             startAng=0, extent=180)
    dome.lineTo(cx - cap_rw, cy)
    dome.close()
    c.drawPath(dome, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    for sx, sy, sr in [
        (cx - cap_rw * 0.42, cy + cap_rh * 0.55, cap_rw * 0.12),
        (cx + cap_rw * 0.10, cy + cap_rh * 0.80, cap_rw * 0.17),
        (cx + cap_rw * 0.50, cy + cap_rh * 0.48, cap_rw * 0.10),
    ]:
        c.circle(sx, sy, sr, fill=1, stroke=0)


# ── Cover ─────────────────────────────────────────────────────────────────────

def draw_cover(c, doc):
    c.saveState()

    # Full dark background
    c.setFillColor(COVER_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Logo photo: full page width, upper portion — no horizontal clipping
    logo_h = 0
    if LOGO_PATH.exists():
        try:
            img  = ImageReader(str(LOGO_PATH))
            iw, ih = img.getSize()
            scale  = min(W / iw, H * 0.48 / ih)
            logo_w = iw * scale
            logo_h = ih * scale
            logo_x = (W - logo_w) / 2
            logo_y = H - logo_h - 1.8*cm
            c.drawImage(str(LOGO_PATH), logo_x, logo_y,
                        width=logo_w, height=logo_h)
        except Exception:
            _draw_mushroom(c, cx=W * 0.75, cy=H * 0.72,
                           cap_rw=4.2*cm, cap_rh=3.2*cm,
                           cap_color=HexColor("#2d5a3a"), stem_color=HexColor("#4a3520"))
            _draw_mushroom(c, cx=W * 0.87, cy=H * 0.58,
                           cap_rw=2.2*cm, cap_rh=1.7*cm,
                           cap_color=HexColor("#3a6845"), stem_color=HexColor("#3d2d1a"))

    # Separator
    sep_y = H - logo_h - 1.8*cm - 4
    c.setFillColor(TAN)
    c.rect(0, sep_y + 3, W, 2, fill=1, stroke=0)
    c.setFillColor(COVER_GREEN)
    c.rect(0, sep_y, W, 1.5, fill=1, stroke=0)

    # Dot grid in text area
    c.setFillColor(HexColor("#1a1510"))
    for row in range(6):
        for col in range(12):
            dot_y = sep_y - 1.5*cm - row * 1.0*cm
            if dot_y > 2.8*cm:
                c.circle(1.8*cm + col * 1.55*cm, dot_y, 1.8, fill=1, stroke=0)

    # Left accent bar
    c.setFillColor(COVER_GREEN)
    c.rect(2.2*cm - 5, sep_y - H * 0.36, 3, H * 0.30, fill=1, stroke=0)

    # Title text — centred
    mid_y = sep_y - 2.2*cm
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(W / 2, mid_y, "Getting Started")
    c.setFillColor(COVER_GREEN)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(W / 2, mid_y - 1.35*cm, "Mushroom Tracker")
    c.setFillColor(TAN)
    c.setFont("Helvetica", 10.5)
    c.drawCentredString(W / 2, mid_y - 2.4*cm, "A step-by-step walkthrough for your first session")

    # Badge
    badge_y = mid_y - 3.8*cm
    c.setFillColor(HexColor("#1a1510"))
    c.roundRect(W / 2 - 3.2*cm, badge_y, 6.4*cm, 1.2*cm, 5, fill=1, stroke=0)
    c.setFillColor(COVER_GREEN)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(W / 2, badge_y + 0.38*cm, "7 steps to first harvest data")

    # Bottom meta
    c.setFillColor(HexColor("#5a4e3a"))
    c.setFont("Helvetica", 8)
    c.drawString(2.2*cm, 2.2*cm, f"Generated {date.today().strftime('%B %d, %Y')}")
    c.drawRightString(W - 2.2*cm, 2.2*cm, "v2.0")

    c.restoreState()


def draw_content(c, doc):
    pass


class CoverPlaceholder(Flowable):
    def wrap(self, aw, ah): return (aw, ah)
    def draw(self): pass


# ── Build ─────────────────────────────────────────────────────────────────────

def build():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.2*cm, bottomMargin=2.4*cm,
        title="Mushroom Tracker -- Getting Started Guide",
        author="Mushroom Tracker",
    )

    cover_frame   = Frame(0, 0, W, H, leftPadding=0, rightPadding=0,
                          topPadding=0, bottomPadding=0)
    content_frame = Frame(2*cm, 2.4*cm, W - 4*cm, H - 4.6*cm, id="content")

    doc.addPageTemplates([
        PageTemplate(id="cover",   frames=[cover_frame],   onPage=draw_cover),
        PageTemplate(id="content", frames=[content_frame], onPage=draw_content),
    ])

    s = []  # story

    s.append(CoverPlaceholder())
    s.append(PageBreak())
    s.append(NextPageTemplate("content"))

    # ── Intro ─────────────────────────────────────────────────────────────────
    s += [
        p("Mushroom Tracker — Getting Started Guide", ms("_gt", fontSize=18,
            textColor=GREEN, fontName="Helvetica-Bold", leading=22, spaceAfter=4)),
        p("This guide walks you through your first complete session — "
          "from the blank setup screen all the way to seeing biological efficiency data "
          "on the report page. Follow the steps in order.", BODY),
        sp(6),
        callout(
            "Open <b>http://localhost:5000</b> in your browser before you begin. "
            "If the server is not running, open a terminal in your Python Scripts "
            "folder and run: <b>python mushroom_app.py</b>",
            label="Before you start:"
        ),
        sp(10),

        # overview checklist
        p("You will complete these 7 steps:", H2),
        sp(4),
    ]

    steps_overview = [
        ("Step 1", "Set up your chamber",           "Name it, set temperature and humidity targets"),
        ("Step 2", "Add your first batch",           "Record substrate recipe, spawn details, dry weight"),
        ("Step 3", "Log an environment reading",     "Your first temperature and humidity entry"),
        ("Step 4", "Update batch status",            "Move the batch through its lifecycle stages"),
        ("Step 5", "Log a flush",                    "Record your first harvest weight and quality"),
        ("Step 6", "Log a sale (optional)",          "Track where the mushrooms went and revenue earned"),
        ("Step 7", "View the report",                "See your BE% ranking and performance summary"),
    ]

    overview_rows = [[
        Paragraph(f"<b>{num}</b>", ms("_on", fontSize=10, textColor=WHITE,
                                       fontName="Helvetica-Bold", leading=13)),
        Paragraph(f"<b>{title}</b>", ms("_ot", fontSize=10, textColor=WHITE,
                                          fontName="Helvetica-Bold", leading=13)),
        Paragraph(desc, ms("_od", fontSize=9, textColor=HexColor("#8b949e"),
                             fontName="Helvetica", leading=13)),
    ] for num, title, desc in steps_overview]

    ov = Table(overview_rows, colWidths=[1.6*cm, 5*cm, W - 4*cm - 6.6*cm])
    ov.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,-1), STEP_BG),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [STEP_BG, HexColor("#161b22")]),
        ("LINEBELOW",      (0,0), (-1,-2), 0.3, HexColor("#30363d")),
        ("LINEBELOW",      (0,-1), (-1,-1), 2, STEP_GREEN),
        ("LEFTPADDING",    (0,0), (-1,-1), 10),
        ("RIGHTPADDING",   (0,0), (-1,-1), 10),
        ("TOPPADDING",     (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 7),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
    ]))
    s.append(ov)
    s.append(sp(8))
    s.append(callout(
        "Each step shows the exact fields to fill in and what to put in them. "
        "You can use your real data or the example values shown -- "
        "everything can be edited later from the batch detail page.",
        label="Tip:", color=BLUE_BG, border=BLUE_BORDER
    ))

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1 — CHAMBER SETUP
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(1, "Set Up Your Chamber",
                    "Configure your fruiting environment — only done once"),
        sp(10),
        p("When you first open the app with a fresh database, you will be redirected to "
          "the <b>Chamber Setup</b> page automatically. Fill in the fields below and click "
          "<b>Save Chamber</b>."),
        sp(8),
        field_table([
            ("Chamber Name",    "A short label for your setup. Example: <b>SGFC-1</b>"),
            ("Location",        "Where it lives. Example: <b>Basement</b>"),
            ("Chamber Type",    "Select the physical setup type from the dropdown. "
                                "Example: <b>Shotgun Fruiting Chamber (SGFC)</b>. "
                                "Used later to compare performance between different chamber types."),
            ("Default Temp",    "Default temperature that pre-fills into every new batch. "
                                "Example: <b>72</b>. You will override this per species "
                                "when you create each batch."),
            ("Default Humidity", "Default RH that pre-fills into every new batch. "
                                "Example: <b>90</b>. Override per species as needed."),
            ("Notes",           "Optional. Anything about the physical setup -- "
                                "container size, perlite depth, hole pattern."),
        ]),
        sp(10),
        p("After saving, you will land on the <b>Dashboard</b>. "
          "It will be empty for now -- that changes in the next steps."),
        sp(8),
        callout(
            "You can edit chamber settings later via the gear icon in the top navigation bar.",
            label="Note:"
        ),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2 — ADD A BATCH
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(2, "Add Your First Batch",
                    "One batch = one fruiting block or bag"),
        sp(10),
        p("From the Dashboard, click <b>+ New Batch</b>. The form has four sections. "
          "Fill in what you know now -- you can always add more detail later."),
        sp(10),

        p("Section 1 — Identity", H3),
        callout(
            "<b>Select Species first</b> from the dropdown. "
            "The Batch Label will auto-fill in the format <b>[CODE]-[NNN]</b> -- "
            "for example, Blue Oyster becomes <b>BO-001</b>, Lions Mane becomes <b>LM-001</b>. "
            "The counter is per species, so your second Blue Oyster batch will be <b>BO-002</b>. "
            "If your species is not in the list, choose <b>Other / Custom</b> and type the name -- "
            "it will be <b>permanently added to the dropdown</b> for all future batches so you never "
            "have to type it again. "
            "You can always edit the label if you need something different.",
            label="Label auto-fill:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(8),
        field_table([
            ("Species",               "Select from the dropdown. Starts with 19 built-in species "
                                       "and grows automatically as you add custom ones. "
                                       "Selecting a species auto-fills the batch label. "
                                       "Not listed? Choose <b>Other / Custom</b> and type the name -- "
                                       "it is permanently saved to the dropdown so it appears as a "
                                       "standard option on every future batch."),
            ("Batch Label",           "Auto-filled as <b>BO-001</b>, <b>LM-001</b>, etc. "
                                       "Edit if needed -- the field is not locked."),
            ("Strain",                "Optional. Specific variety from your supplier. "
                                       "Example: <b>WR-100</b>"),
            ("Inoculation Date",      "When you inoculated. Defaults to today. "
                                       "<b>Sourced block?</b> Leave this blank if you bought the block "
                                       "from a supplier and do not know the inoculation date — "
                                       "the field is optional. Set Status to match the block's "
                                       "actual stage (Colonized or Fruiting) instead of Colonizing."),
            ("Fruiting Chamber Date", "The date you placed the block into your fruiting chamber (SGFC). "
                                       "This is also the signal the AI briefing agent uses to determine "
                                       "whether a block is in the chamber: if this date is set, fruiting "
                                       "environment guardrails apply even if the status is still Colonized. "
                                       "If blank, the block is treated as pre-chamber. "
                                       "For cold-shocking sourced blocks, leave this blank during cold shock "
                                       "and set it the day the block enters the SGFC."),
            ("Sourced / Pre-made Block", "Check this if the block came from a supplier (e.g. North Spore) "
                                          "rather than one you made yourself. "
                                          "Checking this automatically sets the Status to <b>Fruiting</b>. "
                                          "If you are cold-shocking the block first, change Status to "
                                          "<b>Colonized</b> and leave Fruiting Chamber Date blank — "
                                          "set the Fruiting Chamber Date when the block enters the SGFC. "
                                          "The agent uses the Fruiting Chamber Date (not status alone) "
                                          "to decide which guardrails to apply, so two Colonized batches "
                                          "can be correctly evaluated — one in the chamber, one in cold shock. "
                                          "The AI briefing agent will not flag missing substrate, "
                                          "sterilization, or spawn fields. "
                                          "You can still enter estimated dry weight — "
                                          "it will be used for BE% without triggering missing-data alerts."),
            ("Colonization Chamber",  "Only shown if you have more than one chamber. "
                                       "Select the chamber where colonization is happening "
                                       "if it differs from your fruiting chamber."),
            ("Target Temp (F)",       "Ideal fruiting temp for this species. "
                                       "Pre-filled from chamber defaults. "
                                       "Example: <b>68</b> for Blue Oyster, <b>80</b> for Pink Oyster."),
            ("Target Humidity",       "Ideal RH %. Pre-filled from chamber defaults. "
                                       "Example: <b>90</b>."),
            ("Status",                "Leave as <b>Colonizing</b> if mycelium is still spreading."),
        ]),
        sp(10),

        p("Section 2 — Substrate Composition", H3),
        p("Enter the percentage of each ingredient. <b>The percentages must sum to 100.</b> "
          "The form shows a live sum as you type."),
        field_table([
            ("Hardwood %",    "Percentage of hardwood sawdust. Example: <b>85</b>"),
            ("Wheat Bran %",  "Percentage of wheat bran. Example: <b>15</b>"),
            ("Straw %",       "Leave 0 if not using straw."),
            ("Other components", "Coco coir, gypsum, coffee, etc. Free-text with auto-complete — "
                                 "the browser suggests values you have entered on past batches. "
                                 "Example: <b>gypsum 2%, coco coir 8%</b>"),
            ("Substrate Notes", "Qualitative prep observations — separate from the composition fields above. "
                                "Use this for things like <b>used older bran</b> or "
                                "<b>substrate felt drier than usual</b>. "
                                "Keeping this separate preserves the ingredient data for future analysis."),
            ("Dry Weight (g)",
             "<b>Critical for BE% calculations.</b> Weigh your dry ingredients before adding "
             "any water and enter that total here. Example: <b>500</b> for a 500g block."),
        ]),
        sp(6),
        callout(
            "If you skip Dry Weight, BE% will show as -- for this batch. "
            "You can add it later from the batch detail page.",
            label="Important:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    s += [
        sp(10),
        p("Section 3 — Sterilization (optional but recommended)", H3),
        field_table([
            ("Method",        "How you treated the substrate. Example: <b>Pressure cook</b>"),
            ("Temp (F)",      "Temperature used. Example: <b>250</b> (15 PSI pressure cooker)"),
            ("Duration (min)","How long at that temperature. Example: <b>90</b>"),
            ("Flow Hood",     "Check this if you used a laminar flow hood during inoculation."),
        ]),
        sp(10),

        p("Section 4 — Spawn Details (optional but recommended)", H3),
        field_table([
            ("Spawn Type",    "Form of spawn used. Example: <b>Grain</b>"),
            ("Spawn Strain",  "Named variety. Example: <b>Elm Oyster</b>"),
            ("Spawn Rate %",  "Spawn weight as % of dry substrate. Example: <b>15</b>"),
            ("Spawn Source",  "Where the spawn came from. Free-text with auto-complete — "
                              "previously entered suppliers appear as suggestions. "
                              "Example: <b>North Spore</b>"),
            ("Spawn Lot ID",  "Supplier lot number. Useful for tracing contamination back to a bad lot. "
                              "Example: <b>Lot-2026-03</b>"),
        ]),
        sp(10),
        p("Click <b>Save Batch</b>. You will be taken to the <b>Batch Detail</b> page."),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3 — LOG ENVIRONMENT READING
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(3, "Log an Environment Reading",
                    "Record temperature and humidity in your chamber"),
        sp(10),
        p("Click <b>+ Log Reading</b> in the top navigation bar. "
          "Log a reading every day, ideally at the same time each morning. "
          "If you use a <b>Govee H5179</b> sensor, you can bulk-import its history instead -- "
          "click <b>Import Govee CSV</b> on the Environment History page and upload "
          "your Govee app export. Both &deg;F and &deg;C exports are supported, and "
          "re-importing the same file is safe (duplicates are skipped automatically). "
          "Govee-imported readings are also picked up automatically by the AI briefing agent -- "
          "no extra steps needed."),
        sp(8),
        field_table([
            ("Phase",          "Select <b>Colonization</b> if your batch is still colonizing, "
                                "or <b>Fruiting</b> once it has been moved to fruiting conditions."),
            ("Linked Batch",   "Optional. Select your batch to associate this reading with it."),
            ("Temperature (F)","Read from your thermometer probe inside the chamber. "
                                "The form will tell you if you are on target."),
            ("Humidity (% RH)","Read from your hygrometer. Aim for 85-95% during fruiting."),
            ("CO2 (ppm)",      "Skip if you do not have a CO2 meter."),
            ("FAE Fan Cycles", "How many times you fanned or ran a fan today. "
                                "Example: <b>4</b>"),
            ("Misting Count",  "How many times you misted today. Example: <b>3</b>"),
            ("Notes",          "Anything notable -- adjustments made, equipment changed, etc."),
        ]),
        sp(10),
        p("As you type the temperature and humidity, the form shows instant feedback "
          "(<b>Perfect range</b>, <b>Slightly off</b>, <b>Too low -- mist now!</b>). "
          "A preview panel appears once both fields are filled in."),
        sp(8),
        p("Click <b>Save Reading</b>. Back on the Dashboard, "
          "the environment card now shows your reading with a color-coded status."),
        sp(10),
        callout(
            "Build the habit: log once per day, every day. "
            "After two weeks you will have enough data on the Environment History page "
            "to spot overnight humidity drops, temperature spikes, and FAE patterns. "
            "The <b>All Readings</b> table below the chart is collapsible and paginated -- "
            "use the Per Page selector to control how many rows are shown at once.",
            label="Habit tip:"
        ),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4 — UPDATE BATCH STATUS
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(4, "Update Batch Status",
                    "Move your batch through its lifecycle as it progresses"),
        sp(10),
        p("Open the Batch Detail page (click the batch card on the Dashboard, "
          "or go to <b>Batches</b> in the navigation). "
          "The right side of the page has an <b>Update Status</b> section."),
        sp(8),
        p("Update the status whenever something changes:", H3),
        sp(4),
    ]

    lifecycle = [
        ("Colonizing",   "Mycelium spreading through substrate -- default starting state."),
        ("Colonized",    "Full white mycelium coverage. Ready to initiate fruiting conditions. "
                          "Move to your fruiting chamber and increase humidity and FAE."),
        ("Pinning",      "Tiny pin heads are visible. Maintain 85-95% RH and good FAE."),
        ("Fruiting",     "Mushrooms actively growing. Harvest when caps are just before "
                          "fully opening (before the veil tears or edges curl up)."),
        ("Resting",      "Post-harvest. Reduce humidity slightly for 3-7 days then "
                          "return to fruiting conditions for the next flush."),
        ("Done",         "Block is exhausted. Compost or discard. "
                          "Sets block_end_date automatically — used to calculate total cycle length "
                          "and feed per-species averages in the AI briefing."),
        ("Contaminated", "Mold detected. Remove from chamber immediately. "
                          "Select the contamination type when you update."),
    ]

    lc_rows = [[
        Paragraph(f"<b>{stage}</b>", ms("_ls", fontSize=9, textColor=GRAY_DARK,
                                         fontName="Helvetica-Bold", leading=13)),
        Paragraph(desc, ms("_ld", fontSize=9, textColor=GRAY_DARK,
                             fontName="Helvetica", leading=13)),
    ] for stage, desc in lifecycle]

    lc_table = Table(lc_rows, colWidths=[2.8*cm, W - 4*cm - 2.8*cm])
    lc_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, TABLE_ALT]),
        ("LINEBELOW",      (0,0), (-1,-2), 0.3, GRAY_RULE),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("BOX",            (0,0), (-1,-1), 0.5, GRAY_RULE),
    ]))
    s.append(lc_table)
    s += [
        sp(10),
        p("The Batch Detail page shows a visual timeline with the current stage highlighted. "
          "The <b>Colonized date</b> is recorded automatically when you first set that status. "
          "The <b>Pinning date</b> is staged each time you set status to Pinning and "
          "pre-filled into the next flush form — so every flush gets its own accurate pin date "
          "stored on the flush record, not just the first one."),
        sp(8),
        callout(
            "<b>Cold shocking</b> (chilling a colonized block to trigger pinning) does not need "
            "its own status — it only lasts 12-24 hours. Instead, add a note when you set "
            "status to Colonized (<i>cold shocking tonight</i>) or when you set Pinning "
            "(<i>initiated with cold shock on [date]</i>). "
            "This records the information without cluttering the lifecycle.",
            label="Cold shock tip:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(8),
        callout(
            "A typical Blue Oyster timeline: <b>Colonizing 7-14 days</b> &rarr; "
            "<b>Colonized</b> &rarr; <b>Pinning 3-5 days</b> &rarr; "
            "<b>Fruiting 5-7 days</b> &rarr; <b>Harvest</b>. "
            "Your tracker will tell you your actual times after a few batches.",
            label="Reference:"
        ),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 5 — LOG A FLUSH
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(5, "Log a Flush",
                    "Record each harvest event with weight and quality"),
        sp(10),
        p("When you harvest, open the Batch Detail page and click <b>+ Log Flush</b>. "
          "Three live stats at the top show your current BE%, lifetime yield, "
          "and the upcoming flush number."),
        sp(8),
        field_table([
            ("Flush Number",    "Auto-filled with the next number. Leave it as-is for a new flush."),
            ("Harvest Date",    "Defaults to today. Change it if you are recording a past harvest."),
            ("Pinning Date",    "Pre-filled from when you last set the batch status to Pinning. "
                                 "Adjust if needed. Stored on this flush record so every flush "
                                 "has its own pin date — used to calculate days-to-harvest "
                                 "and compare initiation speed across batches and flushes."),
            ("Fresh Weight (g)","<b>Required.</b> Weigh with a kitchen scale immediately after picking. "
                                 "Always use fresh (wet) weight. Example: <b>210</b>"),
            ("Quality Rating",  "Click a number 1-5. Rate the visual quality and pin density. "
                                 "1 = poor (small, malformed, many aborts). "
                                 "5 = excellent (dense clusters, full caps, clean)."),
            ("Notes",           "Pin density, cluster size, any aborts or anomalies noticed."),
        ]),
        sp(10),
        p("As you type the weight, a live preview shows:", H3),
        sp(4),
        *bullet([
            "New total yield after this flush",
            "Updated BE% (if dry weight is recorded on the batch)",
            "A hint: <b>Great flush!</b> / <b>Solid harvest</b> / <b>Small flush</b>",
        ]),
        sp(10),
        p("Click <b>Save Flush</b>."),
        sp(8),
        p("After saving:", H3),
        sp(4),
        *bullet([
            "The batch status is automatically set to <b>Resting</b>",
            "BE% recalculates and the colored pill updates on the batch card",
            "A bar chart appears on the Batch Detail page showing yield per flush",
            "The Report page BE ranking updates with this batch's new score",
        ]),
        sp(10),
        callout(
            "After the rest period (3-7 days), update the batch status back to "
            "<b>Fruiting</b> when new pins appear. Then log another flush when you harvest again. "
            "Most batches give 2-4 flushes total.",
            label="Next steps:"
        ),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 6 — LOG A SALE (OPTIONAL)
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(6, "Log a Sale  (optional)",
                    "Record where mushrooms went and calculate revenue"),
        sp(10),
        p("If you sold, gifted, or used the harvest, click <b>Sales</b> in the "
          "navigation bar, then <b>+ Log Sale</b>."),
        sp(8),
        field_table([
            ("Batch",                 "Select the batch the mushrooms came from."),
            ("Flush",                 "Optional. Link to a specific flush number."),
            ("Sale Date",             "Defaults to today."),
            ("Destination",           "Where they went: <b>Farmers Market</b>, <b>Restaurant</b>, "
                                       "<b>CSA</b>, <b>Personal Use</b>, <b>Gift</b>, or <b>Other</b>."),
            ("Customer",              "Optional. The specific buyer name. "
                                       "Example: <b>Green Acres Restaurant</b> or <b>John Smith</b>. "
                                       "Lets you trace all sales to a particular account over time."),
            ("Fresh Weight Sold (g)", "Grams of fresh mushrooms sold or given away."),
            ("Dried Weight Sold (g)", "Grams of dried mushrooms, if applicable. "
                                       "Fresh-to-dry ratio is roughly 8-12:1 for most species."),
            ("Price per lb (USD)",    "Your selling price. The form calculates revenue live. "
                                       "Typical range: $8-20/lb fresh oysters."),
            ("Notes",                 "Customer name, market name, quality feedback."),
        ]),
        sp(10),
        callout(
            "Revenue = (fresh grams sold / 453.592) x price per lb. "
            "The form shows a live preview as you type. "
            "Sales totals appear in the Report page Sales Summary card.",
            label="Formula:"
        ),
    ]

    s.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 7 — VIEW THE REPORT
    # ══════════════════════════════════════════════════════════════════════════
    s += [
        step_header(7, "View the Report",
                    "See your BE% ranking and full performance summary"),
        sp(10),
        p("Click <b>Report</b> in the navigation bar. "
          "This page is your analytical home -- it updates automatically "
          "as you add more batches and flushes."),
        sp(10),

        p("What you will see:", H3),
        sp(6),
    ]

    report_rows = [
        ["BE% Ranking Table",
         "Every batch ranked from highest to lowest biological efficiency. "
         "Color-coded pills: green (excellent 100%+), teal (good 60-99%), "
         "yellow (average 30-59%), red (poor under 30%). "
         "This is your primary cross-batch KPI."],
        ["Flush Degradation Curve",
         "A line chart with one line per batch. X = flush number, Y = weight. "
         "Appears once any batch has 2+ flushes. "
         "A steep drop means fast substrate exhaustion; a flat line means sustained production."],
        ["Yield by Batch & Flush",
         "A stacked bar chart showing total yield per batch, colored by flush. "
         "Good for comparing total output across batches at a glance."],
        ["Environment Summary",
         "Average, minimum, and maximum temperature and humidity "
         "across all your logged readings."],
        ["Sales Summary",
         "Total revenue, fresh and dried grams sold, "
         "and a breakdown of transaction count by destination."],
    ]

    rr = [[
        Paragraph(f"<b>{name}</b>", ms("_rn", fontSize=9, textColor=GRAY_DARK,
                                        fontName="Helvetica-Bold", leading=13)),
        Paragraph(desc, ms("_rd", fontSize=9, textColor=GRAY_DARK,
                             fontName="Helvetica", leading=13)),
    ] for name, desc in report_rows]

    rt = Table(rr, colWidths=[4.2*cm, W - 4*cm - 4.2*cm])
    rt.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, TABLE_ALT]),
        ("LINEBELOW",      (0,0), (-1,-2), 0.3, GRAY_RULE),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("BOX",            (0,0), (-1,-1), 0.5, GRAY_RULE),
    ]))
    s.append(rt)

    s += [
        sp(12),
        p("After your first batch completes all its flushes, the report will show "
          "a single BE% data point. After 3-5 batches with varying substrate formulas "
          "or strains, the ranking table becomes genuinely useful -- you can see "
          "which recipe produced the best return on substrate invested."),
        sp(10),
        callout(
            "BE% is the number to optimize. "
            "Everything else in the tracker -- substrate percentages, spawn rates, "
            "sterilization methods, environmental readings -- is context that helps you "
            "understand why one batch scored higher than another.",
            label="The goal:"
        ),
        sp(16),
        callout(
            "Made a mistake? Every record can be corrected. "
            "Edit or delete buttons appear on each row in the Flush Log, "
            "Sales tables, and Environment History page. "
            "The batch header also has <b>Edit Batch</b> and <b>Delete</b> buttons. "
            "Deleting a batch removes its flushes and sales — a confirmation dialog "
            "lists exactly what will be removed before anything is deleted.",
            label="Fixing mistakes:"
        ),
        sp(16),
        callout(
            "Want to explore the app without touching real data? "
            "Click the <b>PROD</b> pill in the top-right of the navbar to switch into "
            "<b>Sandbox Mode</b>. "
            "The sandbox is a completely separate database — nothing you do there affects "
            "your production records. An amber banner appears at the top of every page "
            "while you are in sandbox mode so you always know which database is active. "
            "To fill the sandbox with six months of realistic test data, run: "
            "<b>python seed_data.py --sandbox</b>",
            label="Sandbox mode:", color=AMBER_BG, border=AMBER_BORDER
        ),
        sp(16),
        rule(),
        sp(8),
        p("You are set up. From here, your daily routine is:", H2),
        sp(6),
        *action([
            "Log a morning environment reading (<b>+ Log Reading</b>)",
            "Update batch status when something changes (colonized, pinning, fruiting, resting)",
            "Log a flush immediately after each harvest",
            "Check the Report page weekly to see how your BE% is trending",
        ]),
        sp(10),
        sp(10),
        callout(
            "<b>AI Daily Briefing</b> — once you have active batches, click <b>Briefing</b> in "
            "the navigation bar for an AI-generated daily status report. "
            "Claude analyzes all your active batches against species timelines and environmental "
            "readings, then returns a prioritized list of issues, suggested actions, and "
            "pattern observations. Environmental alerts use species-specific and lifecycle-phase-aware "
            "thresholds — a colonizing batch is not evaluated against fruiting humidity standards, "
            "and a Shiitake has different acceptable ranges than an oyster. "
            "Briefings run automatically every morning at 06:00 "
            "while the app is running, or you can trigger one manually with "
            "<b>Run Briefing Now</b>. Requires an Anthropic API key set as the "
            "ANTHROPIC_API_KEY environment variable.",
            label="Bonus feature:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(10),
        p("For detailed reference on any feature, see the companion "
          "<b>mushroom_tracker_guide.pdf</b> in the same folder.",
          ms("_ref", fontSize=10, textColor=GRAY_MID, fontName="Helvetica-Oblique", leading=14)),
    ]

    doc.build(s, canvasmaker=NumberedCanvas)
    print(f"  PDF written to: {OUTPUT}")


if __name__ == "__main__":
    build()
