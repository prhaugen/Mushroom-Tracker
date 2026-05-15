"""
Generates mushroom_tracker_guide.pdf in the same directory.
Run: python generate_guide.py
"""

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate
from reportlab.platypus.flowables import Flowable
from pathlib import Path
from datetime import date


OUTPUT = Path(__file__).parent / "mushroom_tracker_guide.pdf"
W, H = A4

# ── Palette ──────────────────────────────────────────────────────────────────
GREEN       = HexColor("#2d6a4f")
GREEN_LIGHT = HexColor("#52b788")
GREEN_BG    = HexColor("#d8f3dc")
AMBER       = HexColor("#b5890a")
AMBER_BG    = HexColor("#fff3cd")
AMBER_BORDER= HexColor("#f0c040")
RED         = HexColor("#c0392b")
RED_BG      = HexColor("#fde8e8")
RED_BORDER  = HexColor("#e07070")
BLUE        = HexColor("#1a5276")
BLUE_BG     = HexColor("#dbeafe")
BLUE_BORDER = HexColor("#93c5fd")
PURPLE      = HexColor("#6b21a8")
PURPLE_BG   = HexColor("#f3e8ff")
DARK        = HexColor("#1a1a2e")
GRAY_DARK   = HexColor("#333333")
GRAY_MID    = HexColor("#666666")
GRAY_LIGHT  = HexColor("#f5f5f5")
GRAY_RULE   = HexColor("#dddddd")
WHITE       = HexColor("#ffffff")
TABLE_ALT   = HexColor("#f9f9f9")
CODE_BG     = HexColor("#f0f4f0")
CODE_BORDER = HexColor("#c8e6c9")
TAN         = HexColor("#c4a87a")
COVER_BG    = HexColor("#0c0a08")
COVER_GREEN = HexColor("#74c27a")
LOGO_PATH   = Path(__file__).parent / "logo.png.png"


# ── Styles ───────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def make_style(name, parent_name="Normal", **kw):
    parent = base[parent_name]
    return ParagraphStyle(name=name, parent=parent, **kw)

H1 = make_style("H1",
    fontSize=20, textColor=GREEN, spaceAfter=8, spaceBefore=20,
    fontName="Helvetica-Bold", leading=24,
)
H2 = make_style("H2",
    fontSize=14, textColor=GREEN, spaceAfter=6, spaceBefore=14,
    fontName="Helvetica-Bold", leading=18,
)
H3 = make_style("H3",
    fontSize=11, textColor=GRAY_DARK, spaceAfter=4, spaceBefore=10,
    fontName="Helvetica-Bold", leading=14,
)
BODY = make_style("BODY",
    fontSize=10, textColor=GRAY_DARK, spaceAfter=6, spaceBefore=2,
    leading=15, fontName="Helvetica",
)
BODY_SM = make_style("BODY_SM",
    fontSize=9, textColor=GRAY_MID, spaceAfter=4, spaceBefore=0,
    leading=13, fontName="Helvetica",
)
BULLET = make_style("BULLET",
    fontSize=10, textColor=GRAY_DARK, spaceAfter=3, spaceBefore=1,
    leading=15, fontName="Helvetica", leftIndent=14, bulletIndent=0,
)
CODE_STYLE = make_style("CODE_STYLE",
    fontSize=9, textColor=HexColor("#1e4d2b"), spaceAfter=2, spaceBefore=2,
    leading=13, fontName="Courier", leftIndent=0,
)
CAPTION = make_style("CAPTION",
    fontSize=8, textColor=GRAY_MID, spaceAfter=8, spaceBefore=2,
    leading=11, fontName="Helvetica-Oblique", alignment=TA_CENTER,
)
TOC_1 = make_style("TOC_1",
    fontSize=11, textColor=GRAY_DARK, spaceAfter=4, spaceBefore=2,
    leading=14, fontName="Helvetica",
)
TOC_2 = make_style("TOC_2",
    fontSize=10, textColor=GRAY_MID, spaceAfter=3, spaceBefore=0,
    leading=13, fontName="Helvetica", leftIndent=16,
)


def p(text, style=BODY):
    return Paragraph(text, style)

def h1(text): return Paragraph(text, H1)
def h2(text): return Paragraph(text, H2)
def h3(text): return Paragraph(text, H3)
def sp(n=6):  return Spacer(1, n)
def rule():   return HRFlowable(width="100%", thickness=0.5, color=GRAY_RULE, spaceAfter=8, spaceBefore=4)


def bullet(items):
    return [Paragraph(f"&#8226; &nbsp; {item}", BULLET) for item in items]


def code_block(lines):
    rows = [[Paragraph(ln if ln else " ", CODE_STYLE)] for ln in lines]
    t = Table(rows, colWidths=[W - 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), CODE_BG),
        ("BOX",          (0,0), (-1,-1), 0.5, CODE_BORDER),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
    ]))
    return t


def callout(text, color=GREEN_BG, border=GREEN_LIGHT, label=None):
    content = f"<b>{label}</b>  {text}" if label else text
    inner = Paragraph(content, make_style("_cb", fontSize=9, textColor=GRAY_DARK, leading=14))
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


def data_table(headers, rows, col_widths=None, zebra=True):
    header_row = [Paragraph(f"<b>{h}</b>", make_style("_th",
        fontSize=9, textColor=WHITE, leading=12, fontName="Helvetica-Bold")) for h in headers]
    body_rows = []
    for row in rows:
        body_rows.append([Paragraph(str(c), make_style("_td",
            fontSize=9, textColor=GRAY_DARK, leading=13)) for c in row])

    all_rows = [header_row] + body_rows
    t = Table(all_rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), GREEN),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, TABLE_ALT] if zebra else [WHITE]),
        ("LINEBELOW",      (0,0), (-1,0), 0, WHITE),
        ("LINEBELOW",      (0,1), (-1,-1), 0.3, GRAY_RULE),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
    ]))
    return t


# ── Page numbering canvas ─────────────────────────────────────────────────────

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
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        pg = self._pageNumber
        if pg <= 2:
            return
        self.setFont("Helvetica", 8)
        self.setFillColor(GRAY_MID)
        self.drawRightString(W - 2*cm, 1.4*cm, f"Page {pg - 2} of {total - 2}")
        self.drawString(2*cm, 1.4*cm, "Mushroom Tracker v2.0 -- User Guide")
        self.setStrokeColor(GRAY_RULE)
        self.setLineWidth(0.3)
        self.line(2*cm, 1.8*cm, W - 2*cm, 1.8*cm)


# ── Shared mushroom drawing helper ───────────────────────────────────────────

def _draw_mushroom(c, cx, cy, cap_rw, cap_rh, cap_color, stem_color):
    """Draw a toadstool mushroom. (cx, cy) is the base of the cap / top of stem."""
    stem_w = cap_rw * 0.42
    stem_h = cap_rh * 1.1
    # stem
    c.setFillColor(stem_color)
    c.roundRect(cx - stem_w, cy - stem_h, stem_w * 2, stem_h + 2,
                stem_w * 0.7, fill=1, stroke=0)
    # gill underside arc
    c.setStrokeColor(HexColor("#5a4030"))
    c.setLineWidth(0.8)
    path = c.beginPath()
    path.moveTo(cx - cap_rw * 0.75, cy)
    path.curveTo(cx - cap_rw * 0.4, cy + cap_rh * 0.35,
                 cx + cap_rw * 0.4, cy + cap_rh * 0.35,
                 cx + cap_rw * 0.75, cy)
    c.drawPath(path, fill=0, stroke=1)
    c.setLineWidth(1)
    # cap dome
    c.setFillColor(cap_color)
    dome = c.beginPath()
    dome.arc(cx - cap_rw, cy - cap_rh, cx + cap_rw, cy + cap_rh,
             startAng=0, extent=180)
    dome.lineTo(cx - cap_rw, cy)
    dome.close()
    c.drawPath(dome, fill=1, stroke=0)
    # spots
    c.setFillColor(HexColor("#ffffff"))
    for sx, sy, sr in [
        (cx - cap_rw * 0.42, cy + cap_rh * 0.55, cap_rw * 0.12),
        (cx + cap_rw * 0.10, cy + cap_rh * 0.80, cap_rw * 0.17),
        (cx + cap_rw * 0.50, cy + cap_rh * 0.48, cap_rw * 0.10),
    ]:
        c.circle(sx, sy, sr, fill=1, stroke=0)


# ── Cover page ───────────────────────────────────────────────────────────────

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
            # Scale so width fills page; cap so height ≤ 48% of page
            scale  = min(W / iw, H * 0.48 / ih)
            logo_w = iw * scale
            logo_h = ih * scale
            logo_x = (W - logo_w) / 2
            logo_y = H - logo_h - 1.8*cm   # flush near top with small margin
            c.drawImage(str(LOGO_PATH), logo_x, logo_y,
                        width=logo_w, height=logo_h)
        except Exception:
            _draw_mushroom(c, cx=W * 0.77, cy=H * 0.72,
                           cap_rw=4.0*cm, cap_rh=3.1*cm,
                           cap_color=HexColor("#2d5a3a"), stem_color=HexColor("#4a3520"))
            _draw_mushroom(c, cx=W * 0.88, cy=H * 0.58,
                           cap_rw=2.0*cm, cap_rh=1.6*cm,
                           cap_color=HexColor("#3a6845"), stem_color=HexColor("#3d2d1a"))

    # Separator between photo and text area
    sep_y = H - logo_h - 1.8*cm - 4
    c.setFillColor(TAN)
    c.rect(0, sep_y + 3, W, 2, fill=1, stroke=0)
    c.setFillColor(COVER_GREEN)
    c.rect(0, sep_y, W, 1.5, fill=1, stroke=0)

    # Dot grid in text area only
    c.setFillColor(HexColor("#1a1510"))
    for row in range(6):
        for col in range(12):
            dot_y = sep_y - 1.5*cm - row * 1.0*cm
            if dot_y > 2.8*cm:
                c.circle(1.8*cm + col * 1.55*cm, dot_y, 1.8, fill=1, stroke=0)

    # Left accent bar in text area
    c.setFillColor(COVER_GREEN)
    c.rect(2.2*cm - 5, sep_y - H * 0.32, 3, H * 0.28, fill=1, stroke=0)

    # Title text — centred, below the photo
    mid_y = sep_y - 2.4*cm
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(W / 2, mid_y, "Mushroom Tracker")
    c.setFillColor(COVER_GREEN)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W / 2, mid_y - 1.4*cm, "User Guide  v2.0")
    c.setFillColor(TAN)
    c.setFont("Helvetica", 11)
    c.drawCentredString(W / 2, mid_y - 2.5*cm, "Batch & Biological Efficiency Tracking")

    # Bottom meta
    c.setFillColor(HexColor("#5a4e3a"))
    c.setFont("Helvetica", 8)
    c.drawString(2.2*cm, 2.2*cm, f"Generated {date.today().strftime('%B %d, %Y')}")
    c.drawRightString(W - 2.2*cm, 2.2*cm, "v2.0")

    c.restoreState()


def draw_inner_page(c, doc):
    pass


class CoverPlaceholder(Flowable):
    def wrap(self, aw, ah): return (aw, ah)
    def draw(self): pass


# ── TOC rows ──────────────────────────────────────────────────────────────────

def toc_row(num, title, pg):
    level = TOC_1 if "." not in num else TOC_2
    row = Table(
        [[Paragraph(f"{num}&nbsp;&nbsp;&nbsp;{title}", level),
          Paragraph(pg, make_style("_pgn",
              fontSize=10 if "." not in num else 9,
              textColor=GRAY_MID, alignment=TA_RIGHT))]],
        colWidths=[W - 5.5*cm, 1*cm]
    )
    row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 1),
        ("BOTTOMPADDING",(0,0), (-1,-1), 1),
    ]))
    return row


# ── Document build ────────────────────────────────────────────────────────────

def build():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.2*cm, bottomMargin=2.4*cm,
        title="Mushroom Tracker v2.0 User Guide",
        author="Mushroom Tracker",
    )

    cover_frame   = Frame(0, 0, W, H, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    content_frame = Frame(2*cm, 2.4*cm, W - 4*cm, H - 4.6*cm, id="content")

    cover_tpl   = PageTemplate(id="cover",   frames=[cover_frame], onPage=draw_cover)
    content_tpl = PageTemplate(id="content", frames=[content_frame], onPage=draw_inner_page)
    doc.addPageTemplates([cover_tpl, content_tpl])

    story = []

    # Cover page
    story.append(CoverPlaceholder())
    story.append(PageBreak())
    story.append(NextPageTemplate("content"))

    # ══════════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ══════════════════════════════════════════════════════════════════════
    story += [h1("Table of Contents"), rule(), sp(4)]
    toc_entries = [
        ("1",    "Introduction",                                "3"),
        ("2",    "System Overview",                             "3"),
        ("3",    "Getting Started",                             "4"),
        ("3.1",  "Requirements",                                "4"),
        ("3.2",  "Running the Web App",                         "4"),
        ("3.3",  "First-Time Setup",                            "4"),
        ("4",    "Biological Efficiency (BE%)",                 "5"),
        ("4.1",  "What It Is and Why It Matters",               "5"),
        ("4.2",  "BE% Benchmarks by Species",                   "5"),
        ("4.3",  "A Note on Dry Weight",                        "6"),
        ("5",    "The Dashboard",                               "6"),
        ("5.1",  "Harvest Forecast Card",                      "6"),
        ("6",    "Batch Management",                            "7"),
        ("6.1",  "Adding a Batch",                              "7"),
        ("6.2",  "Substrate Composition",                       "8"),
        ("6.3",  "Sterilization Details",                       "8"),
        ("6.4",  "Spawn Details",                               "8"),
        ("6.5",  "Batch Lifecycle",                             "9"),
        ("6.6",  "Updating Batch Status",                       "9"),
        ("6.7",  "Batch Detail Page",                           "10"),
        ("7",    "Logging Flushes",                             "11"),
        ("8",    "Sales Tracking",                              "11"),
        ("9",    "Logging Environment Readings",                "12"),
        ("10",   "Environment History",                         "12"),
        ("11.1", "Chart Controls",                               "13"),
        ("11.2", "All Readings Table",                          "13"),
        ("11.3", "Importing from a Govee H5179 Sensor",         "13"),
        ("11",   "Reports",                                     "14"),
        ("12",   "AI Daily Briefing",                           "14"),
        ("12.1", "What It Does",                                "14"),
        ("12.2", "Requirements",                                "14"),
        ("12.3", "The Briefing Dashboard",                      "14"),
        ("12.4", "Running a Briefing",                          "15"),
        ("12.5", "Reading the Output",                          "15"),
        ("13",   "Culture Tracking",                             "16"),
        ("13.1", "LC Syringe Lots",                             "16"),
        ("14",   "Substrate Batches",                           "17"),
        ("14.1", "Logging a Substrate Run",                     "17"),
        ("14.2", "Linking Blocks to a Substrate Batch",         "18"),
        ("15",   "Grain Jars",                                  "18"),
        ("15.1", "Logging a Grain Jar",                         "18"),
        ("15.2", "Colonization Outcome Outcomes",               "19"),
        ("16",   "Interactive Q&A",                            "19"),
        ("16.1", "Opening the Chat Widget",                    "19"),
        ("16.2", "How It Works",                               "20"),
        ("17",   "Command-Line Interface (CLI)",                "20"),
        ("18",   "Growing Reference",                           "21"),
        ("19",   "Tips & Troubleshooting",                      "23"),
    ]
    for num, title, pg in toc_entries:
        story.append(toc_row(num, title, pg))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 1. INTRODUCTION
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("1. Introduction"),
        rule(),
        p("Mushroom Tracker is a local tracking system for small-scale mushroom cultivation. "
          "It records substrate recipes, spawn details, environmental conditions, per-flush "
          "harvest data, and sales so you can measure and improve your Biological Efficiency (BE%) "
          "over time."),
        sp(),
        p("The system consists of two interfaces sharing a single SQLite database:"),
        sp(4),
        *bullet([
            "<b>Web App</b> — a browser-based dashboard (Flask) for day-to-day use",
            "<b>CLI Tool</b> — a terminal interface for quick logging without a browser",
        ]),
        sp(8),
        callout(
            "Both tools read and write to the same <b>mushroom_data.db</b> file. "
            "Data logged via the CLI appears immediately in the web app and vice versa.",
            label="Note:"
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # 2. SYSTEM OVERVIEW
    # ══════════════════════════════════════════════════════════════════════
    story += [
        sp(12),
        h1("2. System Overview"),
        rule(),
        p("The tracker is organized around five core concepts:"),
        sp(6),
        data_table(
            ["Concept", "What It Tracks", "Key Data"],
            [
                ["Chamber",
                 "Your physical fruiting environment",
                 "Name, location, type (SGFC / Martha Tent / etc.), default temp and humidity targets for new batches"],
                ["Batch",
                 "One fruiting block or bag, from prep through retirement",
                 "Species, strain, substrate recipe, spawn lot, BE%"],
                ["Flush",
                 "A single harvest event from a batch",
                 "Flush number, harvest date, pinning date, weight, quality rating"],
                ["Environment Log",
                 "Point-in-time chamber readings",
                 "Temperature, humidity, CO2, FAE fan cycles, linked batch"],
                ["Sale",
                 "A mushroom sale transaction",
                 "Batch, date, fresh/dried weight sold, price per lb, destination"],
                ["AI Briefing",
                 "Daily AI-generated status report",
                 "Claude analysis of all active batches: attention items with severity, "
                 "environmental alerts, on-track list, pattern observations, and suggested actions"],
            ],
            col_widths=[2.8*cm, 5.2*cm, 8.2*cm],
        ),
        sp(10),
        p("Data flows from Batch (substrate + spawn recipe) through Flush (yield events) "
          "to the Report page where <b>Biological Efficiency</b> ranks every batch by a single "
          "normalized number, making cross-batch and cross-season comparisons straightforward."),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 3. GETTING STARTED
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("3. Getting Started"),
        rule(),
        h2("3.1  Requirements"),
        p("Python 3.9 or later is required. Install the dependencies with:"),
        sp(4),
        code_block([
            "python -m pip install flask rich",
            "",
            "# For the AI Daily Briefing agent:",
            "python -m pip install anthropic apscheduler",
            "",
            "# Optional — to regenerate this PDF guide:",
            "python -m pip install reportlab",
        ]),
        sp(6),
        p("<b>flask</b> powers the web app. <b>rich</b> powers the CLI terminal output. "
          "<b>anthropic</b> is the Python SDK for the Claude API used by the AI briefing agent. "
          "<b>apscheduler</b> runs the 06:00 daily briefing schedule. "
          "The database engine (sqlite3) is part of Python's standard library and requires "
          "no installation."),
    ]

    story += [
        sp(10),
        h2("3.2  Running the Web App"),
        p("Navigate to the folder containing the scripts and run:"),
        sp(4),
        code_block(["python mushroom_app.py"]),
        sp(4),
        p("Then open your browser to <b>http://localhost:5000</b>. "
          "The server runs locally and is only accessible on your machine. "
          "Keep the terminal window open while using the app."),
        sp(4),
        callout("To stop the server, press <b>Ctrl+C</b> in the terminal window.", label="Tip:"),
    ]

    story += [
        sp(10),
        h2("3.3  First-Time Setup"),
        p("The first time you open the web app, you will be redirected to the setup page. "
          "Fill in your chamber details:"),
        sp(6),
        data_table(
            ["Field", "Description", "Suggested Value"],
            [
                ["Chamber Name",    "Short identifier for your setup",                              "SGFC-1"],
                ["Location",        "Where the chamber lives",                                      "Basement"],
                ["Chamber Type",    "Physical setup type — used to filter and compare chamber performance",
                                    "Shotgun Fruiting Chamber, Martha Tent, Incubation Chamber, etc."],
                ["Target Temp",     "Default target temp pre-filled into new batches — override per species on each batch",  "72"],
                ["Target Humidity", "Default target RH pre-filled into new batches — override per species on each batch",    "90"],
                ["Notes",           "Optional — substrate type, hole density, etc.",                "--"],
            ],
            col_widths=[4*cm, 7*cm, 5.2*cm],
        ),
        sp(8),
        p("After saving, you will land on the Dashboard. Add your first batch "
          "using the <b>+ New Batch</b> button."),
    ]

    story += [
        sp(10),
        h2("3.4  Sandbox Mode"),
        p("The app ships with a <b>sandbox database</b> that is completely separate from your "
          "production data. Use it to experiment with new workflows, test bulk imports, or "
          "explore the app without any risk to real records."),
        sp(8),
        data_table(
            ["Element", "Behavior"],
            [
                ["PROD pill (green, top-right navbar)",
                 "You are in production. Click to switch to the sandbox."],
                ["SANDBOX pill (amber, top-right navbar)",
                 "You are in the sandbox. Click to return to production."],
                ["Amber banner (top of every page)",
                 "Visible only in sandbox mode as a persistent reminder."],
                ["'Exit to Production' link",
                 "Appears in the amber banner — one click returns you to production."],
            ],
            col_widths=[6.2*cm, 10*cm],
        ),
        sp(8),
        p("The two databases are completely independent files:"),
        sp(4),
        *bullet([
            "<b>mushroom_data.db</b> — your production database",
            "<b>mushroom_data_sandbox.db</b> — the sandbox; created automatically "
            "the first time you switch into sandbox mode",
        ]),
        sp(8),
        p("To seed the sandbox with six months of realistic test data, run:"),
        sp(4),
        code_block(["python seed_data.py --sandbox"]),
        sp(4),
        p("Running the same command without <b>--sandbox</b> seeds the production database instead. "
          "The sandbox schema is identical to production — every feature works the same way."),
        sp(6),
        callout(
            "Switching databases does not restart the server. The toggle takes effect "
            "immediately and persists for your browser session. "
            "Both databases can exist on disk at the same time without conflict.",
            label="Note:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 4. BIOLOGICAL EFFICIENCY (BE%)
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("4. Biological Efficiency (BE%)"),
        rule(),
        h2("4.1  What It Is and Why It Matters"),
        p("Biological Efficiency (BE%) is the single most important number in this system. "
          "It tells you how much fresh mushroom weight you got per unit of dry substrate invested:"),
        sp(6),
        callout(
            "BE% = (total fresh yield in grams / dry substrate weight in grams) x 100",
            color=GREEN_BG, border=GREEN_LIGHT, label="Formula:"
        ),
        sp(8),
        p("For example: a batch made with 500g of dry substrate that yields 400g total "
          "fresh mushrooms has a BE% of 80%."),
        sp(6),
        p("BE% normalizes yield against the input, so you can directly compare:"),
        sp(4),
        *bullet([
            "Different substrate recipes on the same species",
            "The same recipe across different seasons or chambers",
            "Different strains of the same species",
            "Your operation year-over-year as you refine your process",
        ]),
        sp(8),
        p("The Report page ranks all batches by BE% and color-codes each result:"),
        sp(6),
        data_table(
            ["BE% Range", "Rating", "What It Means"],
            [
                ["100% or above", "Excellent", "Top-tier performance. Substrate fully converted."],
                ["60 - 99%",      "Good",      "Solid result. Room for small gains in recipe or technique."],
                ["30 - 59%",      "Average",   "Typical for early batches. Review substrate and spawn rate."],
                ["Below 30%",     "Poor",      "Investigate substrate quality, contamination, or environmental stress."],
            ],
            col_widths=[3*cm, 2.5*cm, 10.7*cm],
        ),
    ]

    story += [
        sp(12),
        h2("4.2  BE% Benchmarks by Species"),
        sp(4),
        data_table(
            ["Species",       "Typical BE% Range", "Notes"],
            [
                ["Blue Oyster",   "75 - 150%",
                 "One of the highest BE producers. Well-colonized hardwood can exceed 100%."],
                ["Pearl Oyster",  "70 - 140%",
                 "Similar to Blue Oyster. Slightly more forgiving of temperature swings."],
                ["White Oyster",  "70 - 140%",
                 "White strain of P. ostreatus. Near-identical yields to Pearl Oyster."],
                ["Black Oyster",  "70 - 130%",
                 "Cold-fruiting dark strain. High yield, similar to Blue Oyster."],
                ["Pink Oyster",   "60 - 120%",
                 "Warm-weather species (75-85F). Fast colonizer, aggressive fruiter."],
                ["King Oyster",   "70 - 90%",
                 "Valued for thick stems. Low FAE encourages longer, meatier fruiting bodies."],
                ["Lions Mane",    "40 - 100%",
                 "Lower BE than oysters but commands premium pricing. Sensitive to CO2."],
                ["Elm Oyster",    "40 - 80%",
                 "Slower colonizer. Cooler fruiting than other oysters. Less data available."],
                ["Chestnut",      "50 - 100%",
                 "Compact clusters, good shelf life. Less data available than oysters."],
                ["Nameko",        "40 - 80%",
                 "Cold-loving. Glutinous cap. Similar timeline to Shiitake."],
                ["Pioppino",      "30 - 70%",
                 "Dense clusters, cooler temps. Slower than oysters."],
                ["Shiitake",      "40 - 100%",
                 "Blocks require cold shocking to initiate fruiting. Longer colonization time."],
                ["Maitake",       "30 - 70%",
                 "Long colonization. Best on supplemented oak. Less common on substrate blocks."],
                ["Bunashimeji",   "30 - 60%",
                 "Very slow colonizer (45-90 days). Popular commercially; lower hobbyist data."],
                ["Enoki",         "30 - 70%",
                 "Requires cold fruiting chamber. Colonizes at room temp; fruits at 45-55F."],
                ["Wine Cap",      "30 - 80%",
                 "Usually outdoor garden-bed cultivation. BE% varies widely by method."],
                ["Cordyceps",     "10 - 30%",
                 "Stroma (antler) yield by substrate weight. Grown for medicinal value."],
                ["Turkey Tail",   "5 - 20%",
                 "Medicinal species grown for polysaccharides. BE% low by design."],
                ["Reishi",        "10 - 40%",
                 "Low BE is normal -- value is in the antlers/caps, not bulk weight."],
            ],
            col_widths=[3.2*cm, 3.2*cm, 9.8*cm],
        ),
        sp(10),
        callout(
            "These ranges assume properly sterilized substrate, clean grain spawn at 10-20% "
            "spawn rate, and consistent fruiting conditions. Your actual results will vary "
            "and that variance is exactly what this tracker helps you understand.",
            label="Note:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story += [
        sp(10),
        h2("4.3  A Note on Dry Weight"),
        p("The system uses <b>pre-hydration dry weight</b> -- the weight of your substrate "
          "ingredients before any water is added. This is the most consistent and reproducible "
          "measurement because hydration levels vary batch to batch."),
        sp(4),
        p("When you weigh your sawdust, straw, and bran before mixing, record that total as "
          "the batch dry weight. Do not use the weight of the bag after sterilization."),
        sp(6),
        callout(
            "Consistency is what makes BE% useful. If you switch from pre-hydration to "
            "post-hydration weight mid-way through your records, your BE% numbers become "
            "incomparable. Pick pre-hydration and stick with it.",
            label="Important:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 5. THE DASHBOARD
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("5. The Dashboard"),
        rule(),
        p("The Dashboard is your home screen. It gives you an at-a-glance summary of everything "
          "happening in your setup."),
        sp(8),
        h3("Stats Row"),
        p("Four summary cards across the top show:"),
        sp(4),
        *bullet([
            "<b>Avg BE%</b> -- average biological efficiency across all batches with data",
            "<b>Total Yield</b> -- cumulative grams harvested across all batches",
            "<b>Active Batches</b> -- batches not yet marked done or contaminated",
            "<b>Days Running</b> -- days since the earliest inoculation date",
        ]),
        sp(10),
        h3("Environment Card"),
        p("Shows the most recent temperature and humidity reading with color-coded status:"),
        sp(4),
        data_table(
            ["Color", "Meaning"],
            [
                ["Green",  "Reading is within an acceptable range of target"],
                ["Amber",  "Temperature is more than 3F from target -- worth checking"],
                ["Red",    "Humidity is below 80% -- mist your chamber now"],
            ],
            col_widths=[3*cm, 13.2*cm],
        ),
        sp(10),
        h3("Batch Cards"),
        p("A card grid shows all active batches. Each card displays four live metrics: "
          "<b>Days</b> since inoculation, <b>Flushes</b> logged, <b>Yield</b> in grams, "
          "and <b>BE%</b> with its color-coded pill. Click any card to open the full "
          "Batch Detail page."),
        sp(10),
        h3("Recent Flushes"),
        p("A table at the bottom lists the last six flush events across all batches, "
          "with batch name, flush number, weight, and harvest date."),
        sp(10),
        h2("5.1  Harvest Forecast Card"),
        p("When any active batches are present, the dashboard shows a <b>Harvest Forecast</b> "
          "table above Recent Flushes. It projects the harvest window for every active batch "
          "by applying the species timeline midpoints from the growing configuration to "
          "the batch's current lifecycle state."),
        sp(6),
        data_table(
            ["Status", "Projection Basis", "Confidence"],
            [
                ["Colonizing",
                 "Inoculation date + colonization days + days to pin + days to harvest",
                 "Low — weeks of compounding uncertainty"],
                ["Colonized",
                 "Colonization end date + days to pin + days to harvest",
                 "Medium — colonization done, pin timing uncertain"],
                ["Pinning",
                 "Pinning start date + days to harvest",
                 "High — days away"],
                ["Fruiting",
                 "Today — already in harvest window",
                 "Imminent"],
                ["Resting",
                 "Last harvest date + 7 days rest + days to pin + days to harvest",
                 "Medium — next flush projection"],
            ],
            col_widths=[3*cm, 8.8*cm, 4.4*cm],
        ),
        sp(6),
        callout(
            "The <b>Window</b> column shows the earliest-to-latest range using the "
            "low and high ends of the species timeline. The <b>Projected Harvest</b> column "
            "shows the midpoint — treat it as the most likely date, not a guarantee. "
            "Confidence degrades the earlier in the lifecycle a batch is.",
            label="Reading the table:"
        ),
        sp(6),
        callout(
            "By March 2027, this table becomes your market planning tool: "
            "sort active blocks by projected date to confirm whether enough volume "
            "will be in harvest window simultaneously to commit to a market date.",
            label="Planning use:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 6. BATCH MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("6. Batch Management"),
        rule(),
        p("A <b>Batch</b> is the core record in the system -- one fruiting block or bag, "
          "from preparation through retirement. It holds your substrate recipe, spawn details, "
          "and lifecycle status, and accumulates flush data over time."),
        sp(8),
        h2("6.1  Adding a Batch"),
        p("From the Batches page or Dashboard, click <b>+ New Batch</b>. "
          "The form is divided into four sections."),
        sp(6),
        h3("Identity Fields"),
        callout(
            "<b>Select Species first</b> — the form will auto-generate a consistent Batch Label "
            "in the format <b>[SPECIES CODE]-[NNN]</b> (e.g. BO-001, LM-003, SHI-002) "
            "as soon as you make a selection. You can edit the label afterwards if needed. "
            "If your species is not in the dropdown, choose <b>Other / Custom</b> and type the name — "
            "a code will be derived from the initials, and <b>the species is permanently added to the dropdown</b> "
            "for all future batches. No management screen is needed — it accumulates automatically as you use it.",
            label="How labels work:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(8),
        data_table(
            ["Field", "Required", "Notes"],
            [
                ["Species",                   "Yes",
                 "Select from the dropdown. Starts with 19 built-in species; grows automatically "
                 "as you add custom ones. Drives the batch label code and ensures consistent naming. "
                 "If your species is not listed, choose Other / Custom and type the name — "
                 "it is saved to the dropdown permanently so it appears as a standard option on every future batch. "
                 "See the species code table below for all pre-defined entries."],
                ["Batch Label",               "Yes",
                 "Auto-filled from species in the format [CODE]-[NNN]. "
                 "Each species has its own counter: BO-001, BO-002... are all Blue Oyster batches. "
                 "Edit if you need a custom label."],
                ["Strain",                    "No",  "Elm Oyster, WR-100, HK35"],
                ["Inoculation Date",          "No",
                 "Defaults to today. Leave blank if you sourced the block from a supplier "
                 "and do not know when it was inoculated — the field is optional and "
                 "only affects colonization-time calculations, which are not meaningful "
                 "for blocks you did not colonize yourself. Set the Status field to "
                 "reflect the block's actual current stage (Colonized or Fruiting) "
                 "rather than leaving it at Colonizing."],
                ["Fruiting Chamber Date",     "No",
                 "The date the block was placed into the fruiting chamber (e.g. your SGFC). "
                 "This field is also used by the AI briefing agent as the definitive signal "
                 "that a block is in the chamber: if this date is set, the agent applies "
                 "fruiting environment guardrails regardless of the batch status; "
                 "if it is blank, the block is treated as not yet in the chamber. "
                 "This matters most for sourced blocks that are cold-shocking — leave this "
                 "field blank during cold shock and set it the day the block enters the SGFC. "
                 "Displayed under the Colonizing step on the Batch Detail lifecycle timeline."],
                ["Sourced / Pre-made Block",  "No",
                 "Check this if the block was purchased from a supplier (e.g. North Spore) "
                 "rather than prepared in-house. "
                 "Checking this box automatically sets the Initial Status to Fruiting. "
                 "If you are cold-shocking the block before placing it in the chamber, "
                 "change status to Colonized and leave Fruiting Chamber Date blank — "
                 "set the Fruiting Chamber Date the day the block enters the SGFC. "
                 "The AI briefing agent uses the Fruiting Chamber Date (not status alone) "
                 "to determine whether a block is in the chamber: a block with no "
                 "Fruiting Chamber Date is treated as pre-chamber regardless of status. "
                 "The agent will not flag missing substrate composition, sterilization, "
                 "or spawn details — those fields are not applicable for sourced blocks. "
                 "You may still enter estimated dry weight and moisture if known; they will be "
                 "used for BE% calculations without triggering missing-data alerts. "
                 "The Batch Detail page labels the batch as 'sourced block' in the subtitle."],
                ["Fruiting Chamber",          "No",
                 "Which chamber this batch will fruit in. "
                 "When you have more than one chamber configured, a dropdown appears so you can "
                 "assign the batch to any chamber — not just the primary one. "
                 "If only one chamber exists, it is assigned automatically. "
                 "The Chamber Fit Analysis card (see below) recommends the best option "
                 "as soon as you select a species."],
                ["Colonization Chamber",      "No",
                 "The chamber where this batch colonized, if different from the fruiting chamber. "
                 "Only shown when more than one chamber is configured."],
                ["Target Temp (F)",           "No",
                 "Ideal fruiting temp for this species. "
                 "Auto-filled from species defaults when you select a species — "
                 "the hint below the field shows the species default and displays a "
                 "<b>Customized</b> badge if you change the value. "
                 "Clearing the field and re-selecting the species restores the default. "
                 "See Growing Reference for species-specific ranges."],
                ["Target Humidity",           "No",
                 "Ideal RH % for this species. "
                 "Auto-filled from species defaults when you select a species — "
                 "same <b>Customized</b> badge behavior as Target Temp above. "
                 "Drives the dashed reference lines on the Environment History chart "
                 "and on the batch-scoped environment chart on the Batch Detail page."],
                ["Status",                    "No",  "Defaults to Colonizing"],
                ["Notes",                     "No",  "Supplier info, intent, anything relevant"],
            ],
            col_widths=[3.5*cm, 2*cm, 10.7*cm],
        ),
        sp(10),
        callout(
            "<b>Chamber Fit Analysis</b> — When you select a species, an AI-powered fit card "
            "appears automatically in the form. It queries each chamber's last 24 hours of "
            "actual temperature and humidity readings, compares them to the species' fruiting "
            "requirements, and returns a recommendation from Claude with a fit badge: "
            "<b>Ideal</b> (conditions are within the species range), "
            "<b>Good</b> (close and manageable), "
            "<b>Marginal</b> (outside the preferred range but not extreme), or "
            "<b>Poor</b> (conditions would stress this species). "
            "The card also shows 2–3 sentences of reasoning and, when multiple chambers are "
            "configured, a ranked table of all options plus a <b>Use this chamber</b> button "
            "that updates the Fruiting Chamber dropdown. "
            "The recommendation is advisory — you can always override it.",
            label="New:", color=GREEN_BG, border=GREEN_LIGHT
        ),
        sp(10),
        h3("Species Code Reference"),
        p("The following codes are pre-defined. Any species not in this list gets a code "
          "derived automatically from its initials (e.g. Cordyceps Militaris → CM)."),
        sp(6),
        data_table(
            ["Species", "Code", "Species", "Code"],
            [
                ["Blue Oyster",    "BO",  "Shiitake",       "SHI"],
                ["Pearl Oyster",   "PO",  "Chestnut",       "CH"],
                ["Pink Oyster",    "PK",  "Reishi",         "REI"],
                ["Golden Oyster",  "GO",  "Maitake",        "MAI"],
                ["Elm Oyster",     "EO",  "Nameko",         "NAM"],
                ["White Oyster",   "WO",  "Pioppino",       "PIO"],
                ["Black Oyster",   "BLK", "Enoki",          "ENO"],
                ["King Oyster",    "KO",  "Turkey Tail",    "TT"],
                ["Lions Mane",     "LM",  "Wine Cap",       "WC"],
                ["Cordyceps",      "COR", "Bunashimeji",    "BUN"],
            ],
            col_widths=[4.5*cm, 2*cm, 4.5*cm, 2*cm],
        ),
    ]

    story += [
        sp(12),
        h2("6.2  Substrate Composition"),
        p("Record the percentage breakdown of your substrate ingredients. "
          "The percentages must sum to 100 -- the form validates this live and "
          "flags any discrepancy."),
        sp(6),
        data_table(
            ["Field", "Typical Range", "Notes"],
            [
                ["Hardwood %",       "70 - 90%", "Hardwood sawdust (oak, maple, beech). "
                                                  "Primary carbon source for wood-loving species."],
                ["Straw %",          "0 - 50%",  "Wheat straw or rye straw. "
                                                  "Faster colonization, lower overall BE than hardwood."],
                ["Wheat Bran %",     "5 - 20%",  "Nitrogen supplement. Higher bran = faster colonization "
                                                  "but increases contamination risk above 20%."],
                ["Other components", "0 - 30%",  "Coco coir, gypsum, oyster shell, coffee grounds, etc. "
                                                  "Free-text field with auto-complete suggestions from past entries — "
                                                  "each unique value is saved automatically so you do not retype it."],
                ["Substrate Notes",  "—",         "Qualitative prep observations that do not belong in the composition fields above. "
                                                  "Examples: 'used older bran', 'felt drier than usual', 'possible over-hydration'. "
                                                  "Kept separate so ingredient data stays machine-readable for future analysis."],
                ["Dry Weight (g)",   "Required for BE", "Total weight of all dry ingredients before hydration."],
            ],
            col_widths=[3.2*cm, 3.2*cm, 9.8*cm],
        ),
        sp(6),
        callout(
            "You must enter a Dry Weight to unlock BE% calculations. "
            "Without it, the system cannot compute biological efficiency for this batch.",
            label="Important:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story += [
        sp(12),
        h2("6.3  Sterilization Details"),
        p("Recording sterilization parameters helps trace contamination issues back to "
          "preparation rather than fruiting conditions."),
        sp(6),
        data_table(
            ["Field", "Description", "Example"],
            [
                ["Sterilization Method", "How the substrate was treated",
                 "Pressure cook, autoclave, pasteurize, field capacity"],
                ["Temperature (F)",      "Target sterilization temperature",
                 "250F for pressure cooking at 15 PSI"],
                ["Duration (min)",       "Total time at target temperature",
                 "90 minutes (standard for quart jars)"],
                ["Flow Hood Used",       "Whether a laminar flow hood was used",
                 "Check if yes. Reduces contamination risk significantly."],
            ],
            col_widths=[4*cm, 5.5*cm, 6.7*cm],
        ),
    ]

    story += [
        sp(10),
        h2("6.4  Spawn Details"),
        p("Spawn details tie a batch to a specific spawn lot, enabling tracing if a bad lot "
          "causes widespread contamination."),
        sp(6),
        data_table(
            ["Field", "Description", "Example"],
            [
                ["Spawn Type",           "Physical form of the spawn",
                 "Grain, sawdust, liquid culture, agar wedge"],
                ["Spawn Strain",         "Named variety from your supplier",
                 "WR-100, Elm Oyster, HK35, Fossil Oyster"],
                ["Spawn Rate %",         "Spawn weight as percentage of substrate weight",
                 "10-20% is typical. Higher = faster but more expensive."],
                ["Spawn Source/Supplier","Where the spawn came from. Free-text with auto-complete "
                 "suggestions from past entries — each unique supplier is saved automatically.",
                 "North Spore, Field & Forest, local farm"],
                ["Spawn Lot ID",         "Supplier lot or batch number for traceability",
                 "Lot #2026-03-A or internal code"],
            ],
            col_widths=[3.5*cm, 6*cm, 6.7*cm],
        ),
        sp(6),
        callout(
            "If a contamination wave hits multiple batches, check whether they share a spawn lot. "
            "The batch list and report page can be filtered or inspected to identify common lots.",
            label="Tip:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story.append(PageBreak())

    story += [
        h2("6.5  Batch Lifecycle"),
        p("Each batch moves through a defined lifecycle. "
          "The Batch Detail page shows a visual timeline with the current stage highlighted."),
        sp(8),
        data_table(
            ["Stage",        "Badge Color", "What It Means"],
            [
                ["Colonizing",   "Amber",
                 "Mycelium is actively spreading. Keep in a dark, warm location (75-80F optimal)."],
                ["Colonized",    "Blue",
                 "Substrate is fully covered. Ready to initiate fruiting conditions."],
                ["Pinning",      "Purple",
                 "Tiny pin heads are forming. Maintain high humidity and good FAE."],
                ["Fruiting",     "Green",
                 "Mushrooms are actively growing. Harvest before caps begin to curl upward."],
                ["Resting",      "Gray",
                 "Post-harvest rest. Reduce humidity slightly; allow 3-7 days recovery."],
                ["Done",         "Dim",
                 "The block has given all it can. Retire or compost. "
                 "Setting this status automatically records <b>block_end_date</b> — "
                 "the completion date used to calculate total cycle length "
                 "(inoculation to exhaustion). The Batch Detail lifecycle card shows "
                 "the retirement date, total cycle days, cumulative yield, and final BE%."],
                ["Contaminated", "Red",
                 "Mold detected. Remove from the chamber immediately in a sealed bag."],
            ],
            col_widths=[2.8*cm, 2.5*cm, 10.9*cm],
        ),
    ]

    story += [
        sp(10),
        h2("6.6  Updating Batch Status"),
        p("Open the Batch Detail page and use the <b>Update Status</b> section. "
          "Select the new status and optionally add notes."),
        sp(6),
        p("When you select <b>Contaminated</b>, an additional field appears asking for "
          "the contamination type (e.g., Trichoderma, Aspergillus, bacterial wet rot). "
          "Recording this consistently helps you identify recurring patterns -- "
          "for example, green mold often indicates a sterilization or inoculation problem, "
          "while bacterial contamination often points to a substrate moisture issue."),
        sp(8),
        callout(
            "The <b>Colonized date</b> is recorded automatically the first time you set status to Colonized. "
            "The <b>Pinning date</b> works differently: each time you set status to Pinning, the date is "
            "staged internally and pre-filled into the next flush form's Pinning Date field. "
            "This means every flush — not just the first — gets its own accurate pin date, "
            "which is stored on the flush record where it belongs for per-flush analysis. "
            "The <b>Block end date</b> is recorded automatically when you set status to Done — "
            "it enables total cycle time calculation (inoculation to exhaustion) and feeds "
            "the AI agent's per-species average cycle length.",
            label="Note:"
        ),
        sp(8),
        h3("Cold Shocking"),
        p("Cold shocking (exposing a colonized block to cold temperatures to trigger pinning) "
          "does not need its own status. It lasts 12-24 hours and transitions immediately to Pinning, "
          "so creating a dedicated status would just mean two rapid updates with little value in between."),
        sp(4),
        p("The recommended approach:"),
        sp(4),
        *bullet([
            "When setting status to <b>Colonized</b>, add a note: <i>cold shocking tonight</i>",
            "Or when setting status to <b>Pinning</b>, note: <i>initiated with cold shock on [date]</i>",
            "This preserves the information without adding a status that is only ever active for one day",
        ]),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 6.7 BATCH DETAIL PAGE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h2("6.7  Batch Detail Page"),
        p("The Batch Detail page is the main view for a single batch. "
          "It shows the lifecycle timeline, substrate and spawn summary, flush log, sales, "
          "a scoped environment chart, and a discussion log — "
          "all in one place without switching screens."),
        sp(10),
        h3("Environment Chart"),
        p("A dual-axis line chart shows chamber readings for the period the batch has been active, "
          "overlaid with targets and the species' full acceptable range. "
          "Up to six trace lines are drawn:"),
        sp(6),
        data_table(
            ["Trace", "Style", "What It Shows"],
            [
                ["Actual Temp",       "Solid green line",
                 "Temperature readings from the batch's chamber during the batch's active period. "
                 "Plotted on the left y-axis (°F)."],
                ["Actual Humidity",   "Solid blue line",
                 "Humidity readings from the same period. Plotted on the right y-axis (% RH)."],
                ["Target Temp",       "Dashed green line (long dash)",
                 "The batch's saved Target Temp — the ideal fruiting temperature for this species."],
                ["Target Humidity",   "Dashed blue line (long dash)",
                 "The batch's saved Target Humidity — the ideal RH for this species."],
                ["Temp range lo/hi",  "Dotted green lines (short dot, 55% opacity)",
                 "The species' full acceptable temperature range from the Growing Reference. "
                 "Only drawn when the batch species is recognized. "
                 "Readings between these lines are within the acceptable window even if "
                 "they differ from the target; the agent will not recommend adjustments."],
                ["Humidity range lo/hi", "Dotted blue lines (short dot, 55% opacity)",
                 "The species' full acceptable humidity range. Same logic as temp range."],
            ],
            col_widths=[3.2*cm, 3.8*cm, 9.2*cm],
        ),
        sp(8),
        p("Resolution pills above the chart let you switch between 1-minute, 5-minute, "
          "10-minute, 30-minute, and 60-minute averages. "
          "The chart auto-selects a resolution based on the batch's age: "
          "batches under 2 days default to 5m; under 7 days to 10m; otherwise 30m. "
          "Click any pill to override."),
        sp(8),
        callout(
            "The environment chart only shows readings from the batch's assigned chamber "
            "during the batch's active period (inoculation date to today or block end date). "
            "If a batch has no chamber assigned, the chart is hidden.",
            label="Note:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(12),
        h3("Discussion Log"),
        p("The Discussion section at the bottom of the Batch Detail page is a timestamped "
          "log where you can record observations about the batch over time — "
          "similar to the discussion thread on a work item in project-management tools."),
        sp(6),
        *bullet([
            "Type a note and press <b>Add Note</b> — it is saved immediately with a timestamp",
            "Each note's timestamp row has two muted action links: "
            "<b>Edit</b> and <b>Remove</b>. "
            "Clicking <b>Edit</b> replaces the note text with an inline textarea pre-filled with "
            "the current content — no page navigation. "
            "Press <b>Save</b> to commit the change or <b>Cancel</b> to restore the original view. "
            "After saving, the timestamp shows the original creation time plus a smaller "
            "<i>(edited HH:MM)</i> indicator so you always know both when the note was written "
            "and when it was last changed.",
            "Clicking <b>Remove</b> prompts for confirmation before permanently deleting the note. "
            "Use this to remove a note that was accidentally added to the wrong batch.",
            "Notes appear in chronological order, oldest first, with the creation timestamp on each entry",
            "Existing text in the batch's <b>Notes</b> field (from before this feature was added) "
            "is automatically migrated into the Discussion log the first time the app starts",
            "Use discussion notes for things like: <i>first pins visible on left side</i>, "
            "<i>increased misting to 3x/day</i>, <i>hygiene deviation — wiped block surface</i>, "
            "<i>contamination resolved — green spot removed</i>",
        ]),
        sp(8),
        h3("Discussion Notes and the AI Agent"),
        p("The AI Daily Briefing agent reads the last 14 days of discussion notes (up to 10 per batch) "
          "as part of its snapshot. The agent treats these notes as grower ground truth — "
          "they carry more weight than automated alerts:"),
        sp(4),
        *bullet([
            "If a note records that an issue was resolved (e.g. <i>contamination spot removed</i>), "
            "the agent will not re-flag it as an active concern — it moves to Pattern Observations instead",
            "If a note explains an anomaly (e.g. <i>temp spike from opening the door</i>), "
            "the agent factors that in before escalating to a warning",
            "Notes documenting routine hygiene (cleaning, wiping, etc.) are treated as expected grower activity, "
            "not contamination risk signals",
        ]),
        sp(8),
        callout(
            "The Discussion log replaces the old single Notes field on the Update Status form. "
            "Setup notes (entered when the batch was created) still appear in the Substrate card "
            "as read-only setup context.",
            label="Note:"
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 7. LOGGING FLUSHES
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("7. Logging Flushes"),
        rule(),
        p("A <b>Flush</b> is a single harvest event from a batch. "
          "Each batch can have many flushes. Log every picking event -- "
          "even small ones -- to build accurate yield data and BE% calculations."),
        sp(8),
        p("From a batch's detail page, click <b>+ Log Flush</b>. "
          "The form shows three live stats at the top: current BE%, lifetime yield, "
          "and the upcoming flush number."),
        sp(8),
        data_table(
            ["Field", "Required", "Notes"],
            [
                ["Flush Number",        "Yes",
                 "Auto-filled with the next flush number. Override if recording a past event."],
                ["Harvest Date",        "No",
                 "Defaults to today. The date mushrooms were picked."],
                ["Pinning / Initiation Date", "No",
                 "When pins first became visible for this flush. "
                 "Pre-filled automatically from when you last set the batch status to Pinning — "
                 "adjust if the date is not quite right. "
                 "Stored on the flush record so every flush has its own pin date for analysis. "
                 "Used to calculate days-to-harvest per flush."],
                ["Fresh Weight (g)",    "Yes",
                 "Weigh with a kitchen scale. Always use fresh (wet) weight."],
                ["Quality Rating",      "No",
                 "1 (poor) to 5 (excellent). Rate visual quality and pin density."],
                ["Notes",               "No",
                 "Cluster size, aborts, unusual fruiting body shapes, any anomalies."],
            ],
            col_widths=[4*cm, 2*cm, 10.2*cm],
        ),
        sp(10),
        h3("Live BE Preview"),
        p("As you type the flush weight, the form shows a live preview:"),
        sp(4),
        *bullet([
            "New total yield after this flush",
            "Updated BE% if the batch has a dry weight recorded",
            "A hint label: Great flush! / Solid harvest / Small flush",
        ]),
        sp(10),
        h3("Quality Rating"),
        p("The 1-5 quality rating uses a button selector. Buttons fill green up to the "
          "selected number. Use it to track whether flush quality changes over the lifecycle -- "
          "a common pattern is peak quality at flush 1-2, declining by flush 3-4."),
        sp(10),
        h3("After Saving a Flush"),
        *bullet([
            "The batch's total yield and flush count update immediately",
            "BE% recalculates and the colored pill updates on the batch card",
            "The batch status is automatically set to <b>Resting</b>",
            "A bar chart on the Batch Detail page adds this flush to the visual record",
        ]),
        sp(10),
        h3("Multi-Flush Strategy"),
        p("Most batches produce 2-4 flushes before yields decline significantly. "
          "After each harvest, allow 5-7 days of rest (set status to Resting), "
          "then transition back to Fruiting once new pins appear. "
          "When yields drop below roughly 20% of your first flush weight, "
          "or BE% has plateaued, it is usually time to retire the block."),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 8. SALES TRACKING
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("8. Sales Tracking"),
        rule(),
        p("The Sales module lets you record every transaction and calculate revenue from "
          "your harvest. Navigate to <b>Sales</b> in the top navigation to view all transactions, "
          "or click <b>+ Log Sale</b> to record a new one."),
        sp(8),
        h2("Logging a Sale"),
        data_table(
            ["Field", "Required", "Notes"],
            [
                ["Batch",                 "Yes",
                 "Select which batch the mushrooms came from."],
                ["Flush",                 "No",
                 "Optionally link the sale to a specific flush number."],
                ["Sale Date",             "No",  "Defaults to today."],
                ["Destination",           "No",
                 "Farmers market, restaurant, CSA, personal use, gift, other."],
                ["Customer",              "No",
                 "The specific buyer. Examples: Green Acres Restaurant, John Smith, "
                 "Saturday Market Booth 12. Free text -- used to identify who bought what "
                 "across multiple transactions."],
                ["Fresh Weight Sold (g)", "No",
                 "Weight of fresh mushrooms sold in grams."],
                ["Dried Weight Sold (g)", "No",
                 "Weight of dried mushrooms sold. Conversion from fresh is roughly 8-12:1."],
                ["Price per lb (USD)",    "No",
                 "Selling price in dollars per pound of fresh weight. "
                 "Typical retail: $8-20/lb for oysters."],
                ["Notes",                 "No",
                 "Customer name, market location, quality feedback."],
            ],
            col_widths=[4.2*cm, 2*cm, 10*cm],
        ),
        sp(10),
        h3("Revenue Calculation"),
        p("Revenue is calculated automatically as:"),
        sp(4),
        callout(
            "Revenue = (fresh weight sold in grams / 453.592) x price per lb",
            label="Formula:"
        ),
        sp(8),
        p("A live preview in the form updates as you type. "
          "For dried sales, record the dried weight in the dried field "
          "and leave price-per-lb blank (or enter the dried price separately in notes)."),
        sp(10),
        h3("Sales List Page"),
        p("The Sales list page shows three summary stats -- Total Revenue, Fresh Sold, "
          "and Dried Sold -- above a full transaction table. "
          "A breakdown by destination is shown in the Report page Sales Summary card."),
        sp(8),
        callout(
            "Sales data feeds directly into the Report page. Total revenue, "
            "sales by destination, and grams sold appear in the Sales Summary card "
            "alongside your yield and efficiency data.",
            label="Tip:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 9. EDITING AND DELETING RECORDS
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("9. Editing and Deleting Records"),
        rule(),
        p("Every record in the tracker can be corrected or removed after the fact. "
          "Edit/Delete controls appear inline — no separate admin screen is needed."),
        sp(10),

        h2("Where to find the controls"),
        sp(6),
    ]

    edit_rows = [
        ["Chamber settings",
         "Gear icon in the top navigation bar (far right, next to the PROD/SANDBOX pill)."],
        ["Batch details",
         "Batch detail page → Edit Batch and Delete buttons (top-right header). "
         "Deleting a batch removes all its flushes and sales."],
        ["Individual flush",
         "Batch detail page → Flush Log table → Edit / Del buttons on each row."],
        ["Sale record",
         "Sales page or Batch detail page → table row → Edit / Del buttons. "
         "Also accessible from the sales sub-table on the batch detail page."],
        ["Environment reading",
         "Environment History page → table row → Edit / Del buttons."],
    ]

    er = [[
        Paragraph(f"<b>{rec}</b>", make_style("_en", fontSize=9, textColor=GRAY_DARK,
                                               fontName="Helvetica-Bold", leading=13)),
        Paragraph(loc, make_style("_el", fontSize=9, textColor=GRAY_DARK,
                                   fontName="Helvetica", leading=13)),
    ] for rec, loc in edit_rows]

    et = Table(er, colWidths=[3.8*cm, W - 3.8*cm - 3*cm])
    et.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, TABLE_ALT]),
        ("LINEBELOW",      (0,0), (-1,-2), 0.3, GRAY_RULE),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("BOX",            (0,0), (-1,-1), 0.5, GRAY_RULE),
    ]))
    story.append(et)

    story += [
        sp(10),
        h2("Cascade delete rules"),
        sp(6),
        p("Deleting a <b>batch</b> automatically removes all flushes and sales linked to that batch. "
          "Environment readings that referenced the batch have their batch link cleared but are "
          "not deleted — chamber-level readings are preserved."),
        sp(6),
        p("Deleting a <b>flush</b> recalculates the batch totals (total flushes count and total "
          "yield) immediately so that BE% stays accurate."),
        sp(10),
        callout(
            "Batch delete shows a confirmation dialog listing how many flushes and sales "
            "will be removed. All other delete actions also require confirmation. "
            "There is no undo — export or back up your database file "
            "(<b>mushroom_data.db</b>) before bulk deletions.",
            label="Warning:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 10. LOGGING ENVIRONMENT READINGS (renumbered)
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("10. Logging Environment Readings"),
        rule(),
        p("Regular environment logging is the most important daily habit in this system. "
          "It lets you correlate conditions with pinning outcomes and yield results over time. "
          "Aim to log at least once per day, ideally at the same time each morning."),
        sp(8),
        p("Click <b>+ Log Reading</b> in the top navigation bar to open the log form."),
        sp(8),
        data_table(
            ["Field", "Required", "Notes"],
            [
                ["Phase",              "No",
                 "Fruiting, Colonization, or Ambient/Baseline. "
                 "Helps segment your history by lifecycle stage."],
                ["Linked Batch",       "No",
                 "Optionally associate this reading with a specific batch "
                 "rather than the whole chamber."],
                ["Temperature (F)",    "Yes", "Use a digital probe thermometer placed inside the chamber."],
                ["Humidity (% RH)",    "Yes",
                 "Use a digital hygrometer. Analog gauges are often inaccurate."],
                ["CO2 (ppm)",          "No",
                 "Requires a CO2 meter. Normal fresh air is ~400 ppm. "
                 "Above ~1000 ppm can delay or prevent pinning."],
                ["FAE Fan Cycles/Day", "No",
                 "Number of fanning or fan-on cycles per day. "
                 "Proxy for CO2 if you do not have a meter. Aim for 4-6x/day for fruiting."],
                ["Light Hours",        "No",  "Hours of light exposure in the past 24 hours."],
                ["Misting Count",      "No",  "How many times you misted today."],
                ["Notes",              "No",  "FAE adjustments, equipment changes, observations."],
            ],
            col_widths=[4*cm, 2*cm, 10.2*cm],
        ),
        sp(10),
        h3("Live Feedback"),
        p("As you type, the form shows instant feedback:"),
        sp(4),
        *bullet([
            "<b>Perfect range</b> -- within 2F of target temperature",
            "<b>Slightly off target</b> -- within 4F of target temperature",
            "<b>Far from target</b> -- more than 4F deviation",
            "<b>Excellent humidity</b> -- 85% RH or above",
            "<b>Consider misting</b> -- 75-84% RH",
            "<b>Too low -- mist now!</b> -- below 75% RH",
        ]),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # 10. ENVIRONMENT HISTORY
    # ══════════════════════════════════════════════════════════════════════
    story += [
        sp(12),
        h1("11. Environment History"),
        rule(),
        p("The Environment page shows a dual-axis line chart plotting temperature (amber) "
          "and humidity (blue) for a selectable date and time range. "
          "Dashed lines show the target temperature and humidity for the most recently active batch -- "
          "the y-axes automatically expand to keep the target lines visible even when the chamber "
          "is running above or below the target. "
          "Below the chart, the All Readings table lists every reading with color-coded values."),
        sp(8),
        *bullet([
            "Temperature values more than 3F from the batch target display in <b>amber</b>",
            "Humidity values below 80% display in <b>red</b>",
            "In-range values display in <b>green</b>",
            "The chart header shows the number of data points currently plotted",
            "The chart title notes which batch the target lines are drawn from",
        ]),
        sp(8),
        p("Because targets are stored per batch rather than per chamber, the reference "
          "lines automatically reflect the needs of whatever species is currently active -- "
          "Pink Oyster at 80F shows a different target line than Blue Oyster at 68F, "
          "even if both ran in the same chamber."),
        sp(6),
        p("Use this page to spot patterns -- for example, if humidity consistently drops "
          "overnight, you may need to add more perlite or mist before bed. "
          "If you can see pinning events on the batch detail pages, try to correlate "
          "them with specific environmental conditions to find your personal recipe."),
        sp(10),
        h2("11.1  Chart Controls"),
        p("A control bar above the chart lets you zoom into any time window and adjust "
          "the resolution to match your sensor's data density."),
        sp(6),
        data_table(
            ["Control", "Behavior"],
            [
                ["From / To",
                 "Date and time pickers that define the chart window. "
                 "Set any range -- an hour, a day, a week -- and click <b>Apply</b>. "
                 "Defaults to the last 24 hours on page load."],
                ["Resolution (1m / 5m / 10m / 30m / 60m)",
                 "How readings are averaged before plotting. "
                 "At 1-minute sensor resolution, use 1m or 5m for short windows "
                 "and 30m or 60m for multi-day ranges to keep the chart readable. "
                 "Clicking a resolution pill applies immediately without needing Apply."],
                ["Apply button",
                 "Reloads the chart with the selected From / To range and current resolution."],
            ],
            col_widths=[4.2*cm, 12*cm],
        ),
        sp(8),
        callout(
            "The chart and the All Readings table below it are independent. "
            "Changing the chart range or resolution does not affect the table, "
            "which always shows all readings paginated.",
            label="Note:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story += [
        sp(10),
        h2("11.2  All Readings Table"),
        p("Below the chart, the <b>All Readings</b> panel lists every stored environment reading "
          "in reverse-chronological order. The table is collapsible and paginated so it stays "
          "manageable as your reading count grows."),
        sp(6),
        data_table(
            ["Control", "Behavior"],
            [
                ["Collapse toggle (chevron)",
                 "Click the All Readings header to collapse or expand the table. "
                 "The collapsed state is remembered in your browser across page reloads."],
                ["Per page selector",
                 "Choose 25, 50, 100, or All rows per page. "
                 "Your selection is saved in the browser and restored on your next visit."],
                ["Page number pills",
                 "Click any page number to jump directly to it. "
                 "Prev / Next and first / last buttons are also provided."],
            ],
            col_widths=[4.2*cm, 12*cm],
        ),
    ]

    story += [
        sp(10),
        h2("11.3  Importing from a Govee H5179 Sensor"),
        p("If you use a Govee H5179 WiFi temperature and humidity sensor, you can bulk-import "
          "its history directly from a CSV export rather than logging readings manually. "
          "Click the <b>Import Govee CSV</b> button on the Environment History page."),
        sp(6),
        h3("How to export from the Govee app"),
        *bullet([
            "Open the Govee Home app and tap your H5179 device",
            "Tap the graph icon to open the history view",
            "Select a date range",
            "Tap <b>Export</b> -- the app saves a .csv file to your device",
        ]),
        sp(8),
        data_table(
            ["Feature", "Detail"],
            [
                ["Unit detection",
                 "The importer reads the column header to determine whether temperature "
                 "is in Fahrenheit or Celsius and converts automatically. "
                 "Both export formats from the Govee app are supported."],
                ["Deduplication",
                 "Rows whose timestamp already exists for the selected chamber are skipped. "
                 "Re-importing the same file is safe -- no duplicate rows will be created."],
                ["Result summary",
                 "After import a flash message reports exactly how many rows were inserted "
                 "and how many were skipped as duplicates."],
                ["Column detection",
                 "Column order does not matter. The importer finds columns by keyword: "
                 "Time/Date for the timestamp, Temp for temperature, Humid for humidity."],
                ["Phase",
                 "All imported rows are tagged with phase = fruiting. "
                 "Edit individual readings afterwards if a different phase applies."],
                ["AI Briefing integration",
                 "Govee-imported readings are automatically included in the AI Daily Briefing's "
                 "environmental analysis. The agent queries sensor data by chamber, so all imported "
                 "rows feed into daily alerts and out-of-range detection — "
                 "no extra steps are needed after importing."],
            ],
            col_widths=[3.5*cm, 12.7*cm],
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 11. REPORTS
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("12. Reports"),
        rule(),
        p("The Report page is the analytical center of the system. "
          "It aggregates all your batch, flush, environment, and sales data "
          "into a single performance summary."),
        sp(8),
        h3("BE% Ranking Table"),
        p("The primary element on the report page. Every batch with yield data is ranked "
          "from highest to lowest Biological Efficiency. Columns include:"),
        sp(4),
        *bullet([
            "Batch label and species",
            "Strain and substrate composition summary (HW / Straw / Bran percentages)",
            "Dry substrate weight",
            "Total fresh yield",
            "BE% pill (color-coded: excellent / good / average / poor)",
            "Total flush count",
            "Current status",
        ]),
        sp(8),
        p("This table is your primary tool for comparing recipes and strains. "
          "If two batches share the same species but different substrate formulas, "
          "their relative BE% directly shows which recipe performed better."),
        sp(10),
        h3("Flush Degradation Curve"),
        p("A line chart with one line per batch, x-axis = flush number, "
          "y-axis = weight in grams. "
          "A steep downward curve means the substrate was exhausted quickly. "
          "A flat or slowly declining line means the block is sustaining well. "
          "Only batches with 2 or more flushes appear on this chart."),
        sp(10),
        h3("Yield by Batch and Flush"),
        p("A stacked bar chart showing total yield per batch, colored by flush number. "
          "This makes it easy to compare total yield across batches "
          "and see which flush contributed the most to each batch."),
        sp(10),
        h3("Environment Summary"),
        p("Average, minimum, and maximum temperature and humidity across all logged readings. "
          "Use the min/max values to see how wide your swings are -- "
          "tighter control generally correlates with better BE%."),
        sp(10),
        h3("Sales Summary"),
        p("Total revenue, total fresh grams sold, total dried grams sold, "
          "and a breakdown of transaction count by destination "
          "(farmers market, restaurant, CSA, personal use, etc.)."),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 12. AI DAILY BRIEFING
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("12. AI Daily Briefing"),
        rule(),
        p("The AI Daily Briefing is a one-page status report generated by Claude that analyzes "
          "all your active batches and environmental data and returns a prioritized list of "
          "issues, suggested actions, and pattern observations. It is designed to give you a "
          "single daily read that surfaces anything that needs attention without requiring "
          "you to review each batch individually."),
    ]

    story += [
        sp(10),
        h2("12.1  What It Does"),
        p("Each time a briefing runs, the system collects a full snapshot of your grow:"),
        sp(4),
        *bullet([
            "All active batches with their lifecycle status, days in current stage, and flush history",
            "Last 24 hours of environmental readings per batch or chamber — including sensor imports "
            "from the Govee CSV importer, which are linked by chamber rather than batch — "
            "with out-of-range streak detection using per-batch, phase-aware, species-specific thresholds",
            "Up to 10 discussion notes per batch from the last 14 days — "
            "grower observations logged via the Discussion panel on the Batch Detail page. "
            "These are treated as ground truth: a note recording that an issue was resolved "
            "prevents the agent from re-flagging it as an active concern",
            "Your historical averages per species — average BE%, colonization days, "
            "total cycle days (inoculation to block retirement), flush count, and "
            "days to first pin — used once you have 5+ completed batches per species",
            "Species timelines and expected performance benchmarks",
        ]),
        sp(6),
        p("That snapshot is sent to Claude, which returns a structured briefing with five parts: "
          "a plain-language summary, an attention list, environmental alerts, an on-track list, "
          "and pattern observations. The result is saved to the database and displayed on the "
          "Briefing page."),
    ]

    story += [
        sp(10),
        h2("12.2  Requirements"),
        p("The briefing agent requires two dependencies and one environment variable:"),
        sp(6),
        data_table(
            ["Requirement", "How to Set Up"],
            [
                ["anthropic package",
                 "Install with: python -m pip install anthropic apscheduler"],
                ["ANTHROPIC_API_KEY",
                 "Set as a Windows user environment variable. "
                 "Get your key from console.anthropic.com. "
                 "The app reads this automatically on startup — no config file needed."],
                ["apscheduler package",
                 "Installed alongside anthropic (same pip command above). "
                 "Powers the 06:00 daily schedule. "
                 "If not installed, the scheduler is silently disabled but manual runs still work."],
            ],
            col_widths=[4*cm, 12.2*cm],
        ),
        sp(8),
        callout(
            "If ANTHROPIC_API_KEY is not set, clicking 'Run Briefing Now' will show an error. "
            "The scheduler will also fail silently. Set the key and restart the app.",
            label="Note:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story += [
        sp(10),
        h2("12.3  The Briefing Dashboard"),
        p("Navigate to <b>Briefing</b> in the top navigation bar. "
          "The page shows the most recent briefing for today, or the most recent date "
          "that has one."),
        sp(6),
        h3("7-Day History Nav"),
        p("A row of date pills at the top lets you navigate to any of the last seven "
          "days that have a saved briefing. Each pill shows a badge:"),
        sp(4),
        data_table(
            ["Badge", "Meaning"],
            [
                ["Red number",    "Critical items found on that date — needs immediate attention"],
                ["Amber number",  "Attention-required items found (warnings or info)"],
                ["Green checkmark", "All batches on track — no issues found"],
            ],
            col_widths=[3.5*cm, 12.7*cm],
        ),
    ]

    story += [
        sp(10),
        h2("12.4  Running a Briefing"),
        sp(4),
        data_table(
            ["Method", "How", "When It Runs"],
            [
                ["Automatic",
                 "Runs in the background while the Flask app is running",
                 "Every day at 06:00. No action needed."],
                ["Manual (web)",
                 "Click the <b>Run Briefing Now</b> button on the Briefing page",
                 "Immediately. Overwrites today's briefing if one already exists."],
                ["Manual (CLI)",
                 "Run: python mushroom_agent.py",
                 "Immediately. Saves result to the database. "
                 "Prints a summary to the terminal."],
            ],
            col_widths=[2.8*cm, 7*cm, 6.4*cm],
        ),
        sp(8),
        callout(
            "Re-running a briefing on the same day overwrites the previous result. "
            "If environmental conditions changed significantly since the morning run, "
            "trigger a manual run to get an updated assessment.",
            label="Tip:", color=BLUE_BG, border=BLUE_BORDER
        ),
    ]

    story += [
        sp(10),
        h2("12.5  Reading the Output"),
        p("The briefing is divided into five sections:"),
        sp(6),
        data_table(
            ["Section", "What It Contains"],
            [
                ["Summary",
                 "A two or three sentence plain-language overview of the current state of all batches. "
                 "Three stat boxes show total critical, total attention, and total on-track counts."],
                ["Attention Required",
                 "Each item has a batch link, species, a plain-language description of the issue, "
                 "a severity badge, and a suggested action. "
                 "Severity levels: <b>Critical (red)</b> = immediate action needed; "
                 "<b>Warning (amber)</b> = monitor closely; <b>Info (blue)</b> = observation worth noting. "
                 "Severity is calibrated to context: a hygiene event on a fruiting block (surface wipe, "
                 "minor spot) is flagged as Warning, not Critical — the block is already producing, "
                 "and the response is monitoring, not removal. "
                 "A fully colonized block gets lower severity than a freshly inoculated one for similar deviations. "
                 "The agent only flags something here if it is actionable today — "
                 "it avoids re-raising issues that your discussion notes indicate are already resolved."],
                ["Environmental Alerts",
                 "Out-of-range readings that persisted for 2+ consecutive hours in the last 24 hours. "
                 "Shows the parameter, observed value, expected range, and duration. "
                 "Temperature, humidity, and CO2 are all monitored. "
                 "Thresholds are per-batch: the agent uses each batch's actual lifecycle status "
                 "(colonizing, pinning, fruiting, resting) and species-specific targets — "
                 "so a Shiitake fruiting at 83% RH is not flagged (its target is 80-90%), "
                 "while a Blue Oyster at the same reading would be (its target is 85-95%). "
                 "A colonizing batch is evaluated against colonization standards, not fruiting ones. "
                 "The Fruiting Chamber Date field is the definitive signal: if set, the block "
                 "is in the chamber and fruiting guardrails apply even if status is still Colonized. "
                 "If blank, the block is treated as an intentional pre-chamber hold — "
                 "either in cold shock or awaiting placement — and colonization guardrails apply. "
                 "The agent will NOT prompt you to confirm placement or flag the missing date as a "
                 "data gap; it understands this is normal grower workflow. "
                 "This allows two Colonized batches to be evaluated correctly at the same time — "
                 "one in the SGFC with fruiting guardrails, one in cold shock with colonization guardrails."],
                ["On Track",
                 "Batches with no issues. Shown as green pills linking directly to each batch detail page."],
                ["Pattern Observations",
                 "Cross-batch patterns Claude noticed that do not rise to the level of an alert. "
                 "Examples: colonization times trending slower than your historical average, "
                 "flush yields declining faster than normal across multiple batches. "
                 "Cleared flags also appear here: if your discussion notes indicate an issue was resolved, "
                 "the agent moves it to Pattern Observations as a historical note rather than carrying it "
                 "forward in Attention Required."],
            ],
            col_widths=[3.5*cm, 12.7*cm],
        ),
        sp(8),
        callout(
            "The agent uses the species' <b>full acceptable range</b> — not just the midpoint target — "
            "as its acceptable window when evaluating environmental readings. "
            "If a reading is within the species range, the agent will not recommend adjusting "
            "temperature or humidity even if the reading differs from the batch target. "
            "For example: Blue Oyster's acceptable range is 55–70°F. "
            "A chamber running at 66.7°F is well within that range, so the agent treats it as normal "
            "and will not flag it or recommend nudging toward the 62.5°F midpoint target. "
            "Only readings outside the full species range trigger environmental guidance.",
            label="Range vs. target:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(8),
        callout(
            "The agent compares your batches against your own historical averages once you have "
            "5 or more completed batches for a given species. Before that threshold, it falls back "
            "to the built-in species timelines. The more data you accumulate, the more "
            "personalized the analysis becomes.",
            label="How it learns:"
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 13. CULTURE TRACKING
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("13. Culture Tracking"),
        rule(),
        p("The Culture section tracks the upstream inputs to your grow — the liquid culture "
          "syringes, agar plates, and grain jars that become your fruiting blocks. "
          "This section documents the first piece of that chain: LC syringe lots."),
        sp(8),
        h2("13.1  LC Syringe Lots"),
        p("Navigate to <b>Culture</b> in the top navigation bar to view and manage your "
          "LC syringe lot records. Each record represents one order from a vendor — a "
          "distinct lot of liquid culture for a specific species."),
        sp(6),
        callout(
            "Start logging lots before you inoculate your first grain jars. "
            "Retrofitting lot numbers onto grain jar records after the fact is lossy — "
            "lot-level traceability only works if the lot is recorded at order time.",
            label="Timing:", color=AMBER_BG, border=AMBER_BORDER
        ),
        sp(8),
        h3("Fields"),
        sp(4),
        data_table(
            ["Field", "Required", "Notes"],
            [
                ["Vendor",      "Yes",
                 "Supplier name. Used to group lots for cross-vendor comparisons."],
                ["Species",     "Yes",
                 "Mushroom species. Selects from the same species list as batches."],
                ["Order Date",  "No",
                 "Date the order was placed or received. Used for lot age tracking."],
                ["Lot Number",  "No",
                 "The vendor's internal lot or batch identifier. This is the critical "
                 "traceability field — record it exactly as printed on the packaging."],
                ["Media Type",  "No",
                 "The liquid culture growth medium (e.g. Potato Dextrose Broth, "
                 "Malt Extract Broth, Coconut Water). Affects colonization vigor."],
                ["Notes",       "No",
                 "Free text for observations, supplier links, or colonization results."],
            ],
            col_widths=[3.2*cm, 2.2*cm, 10.8*cm],
        ),
        sp(10),
        h3("Why Lot Numbers Matter"),
        p("Lot number is the unit of traceability. A vendor may ship multiple lots "
          "of different quality in the same month. If colonization fails across several "
          "grain jars, the lot number tells you whether all failures share a common "
          "source — a question you cannot answer if you only recorded the vendor name."),
        sp(4),
        callout(
            "When a lot produces poor colonization, search all grain jar records linked "
            "to that lot ID to calculate the contamination rate. A single bad lot is a "
            "vendor quality issue; a pattern across lots is a workflow issue on your end.",
            label="Diagnostic:"
        ),
        sp(10),
        h3("Transitioning to Own-Culture LC"),
        p("When you begin producing your own liquid culture from agar plates "
          "(Phase 4, target February 2027), the same LC Lots table carries forward. "
          "Set Vendor to <b>own culture</b> and Lot Number to the source block's "
          "batch label (e.g. <i>BO-007</i>). The data model does not change at "
          "the transition — only the source of the culture changes. "
          "Yield comparisons before and after the transition are a direct query: "
          "group BE% by own-culture lots vs. purchased lots."),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 14. SUBSTRATE BATCHES
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("14. Substrate Batches"),
        rule(),
        p("A substrate batch is one preparation run — a specific mix of ingredients "
          "sterilized together at the same time. Multiple fruiting blocks inoculated "
          "from the same substrate run share a substrate batch record. "
          "Navigate to <b>Substrate</b> in the top navigation bar to log and manage runs."),
        sp(6),
        callout(
            "The most important contamination diagnostic this enables: "
            "<b>did all the contaminated blocks this week come from the same substrate batch?</b> "
            "If yes, the cause is in the substrate prep — sterilization, field capacity, or cooldown. "
            "If no, the cause is environmental or spawn-related. "
            "This query is impossible without substrate batch as a first-class entity.",
            label="Why it matters:"
        ),
        sp(10),
        h2("14.1  Logging a Substrate Run"),
        p("Click <b>+ New Substrate Batch</b> on the Substrate page. "
          "Fill in the preparation details for the entire run — not for individual blocks. "
          "All blocks inoculated from this run will link back to this record."),
        sp(6),
        data_table(
            ["Field", "Notes"],
            [
                ["Date Prepared",
                 "Date the substrate was mixed and sterilized."],
                ["Substrate Type",
                 "Free-text label for the recipe — e.g. Master's Mix, Supplemented Sawdust. "
                 "Common types are suggested in a dropdown."],
                ["Dry Weight (g)",
                 "Total dry substrate weight for the entire run before hydration. "
                 "Required for BE% calculation on all blocks linked to this run."],
                ["Field Capacity %",
                 "Target moisture percentage. Aim for 60–65% for most hardwood substrates."],
                ["Component Percentages",
                 "Hardwood, Straw, Bran, Gypsum, Coco Coir, and Other. "
                 "A live sum checker confirms they total 100%."],
                ["Sterilization Method",
                 "Pressure cooker, autoclave, pasteurization, lime treat, cold water, or none."],
                ["Sterilization Temp (F) / Duration (min)",
                 "Actual values used — not targets. Record what happened, not what was planned."],
                ["Cooldown Duration (min)",
                 "Time from pressure cooker off to inoculation. "
                 "Insufficient cooldown is a common contamination root cause — "
                 "inoculating into still-warm substrate kills or stresses the spawn."],
                ["Notes",
                 "Qualitative observations: substrate felt drier than usual, "
                 "used older bran, bag weight after hydration, etc."],
            ],
            col_widths=[4.5*cm, 11.7*cm],
        ),
        sp(10),
        h2("14.2  Linking Blocks to a Substrate Batch"),
        p("When adding or editing a batch, the <b>Substrate Composition</b> section "
          "shows a <b>Link to Substrate Batch</b> dropdown at the top. "
          "Select the run this block came from to:"),
        sp(4),
        *bullet([
            "Auto-fill all substrate fields from the run record — dry weight, moisture, "
            "component percentages, sterilization method, temp, and duration.",
            "Link the block to the run for contamination diagnostics. "
            "The Substrate page shows how many blocks are linked to each run.",
        ]),
        sp(6),
        p("Fields remain fully editable after auto-fill. If one block in a run used "
          "a different inoculation rate or had a different actual dry weight, "
          "override the field — the substrate batch record captures the run-level defaults, "
          "the batch record captures what actually happened per block."),
        sp(6),
        callout(
            "Log the substrate batch <b>before</b> adding the blocks, not after. "
            "The selector only shows existing runs — if the run isn't logged yet, "
            "there is nothing to link to and each block gets entered redundantly.",
            label="Workflow tip:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 15. GRAIN JARS
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("15. Grain Jars"),
        rule(),
        p("Grain jars are the intermediate step between an LC lot and a substrate batch. "
          "Each jar is inoculated from a liquid culture source, colonizes the grain, "
          "and is then broken into a substrate batch to inoculate the blocks. "
          "Recording grain jars closes the full traceability chain:"),
        sp(4),
        callout(
            "<b>LC lot → grain jar → substrate batch → fruiting block → flush</b><br/>"
            "Every hop is queryable. A contamination wave on fruiting blocks can be traced "
            "back through substrate batch → grain jars → LC lot → vendor in a single join path.",
            label="Traceability chain:", color=GREEN_BG, border=GREEN_LIGHT
        ),
        sp(8),

        h2("15.1  Logging a Grain Jar"),
        p("Navigate to <b>Grain</b> in the nav bar and click <b>+ Add Jar</b>. "
          "Each jar record captures:"),
        sp(4),
        data_table(
            ["Field", "Purpose"],
            [
                ["LC Lot",
                 "Link to the LC lot (vendor, species, lot number) this jar was inoculated from. "
                 "Optional — use Spawn Source as free text if no lot record exists yet."],
                ["Spawn Source",
                 "Free-text fallback when no LC lot record is selected. "
                 "Also useful for own-culture notes, e.g. 'own culture BO-007'."],
                ["Species",
                 "Species being grown in this jar. Required."],
                ["Inoculation Date",
                 "Date the grain was inoculated. Used to calculate days-to-colonization."],
                ["Full Colonization Date",
                 "Date the jar reached full colonization. Leave blank until complete. "
                 "The list page shows elapsed days for in-progress jars."],
                ["Outcome",
                 "Clean / Contaminated / Slow / Partial. "
                 "Used to calculate clean rate per LC lot."],
                ["Used In Substrate Batch",
                 "Link to the substrate batch this jar was used to inoculate. "
                 "Closes the grain jar → substrate batch hop in the traceability chain."],
            ],
            col_widths=[5.0*cm, 11.2*cm],
        ),
        sp(8),

        h2("15.2  Colonization Outcome Codes"),
        data_table(
            ["Outcome", "Meaning"],
            [
                ["Clean",
                 "Full colonization, no visible contamination. "
                 "Jar is suitable for substrate inoculation."],
                ["Contaminated",
                 "Visible mold, bacterial wet rot, or other contamination. "
                 "Jar should be discarded. Contributes to contam rate for the LC lot."],
                ["Slow",
                 "Colonizing but significantly behind expected timeline. "
                 "May indicate weak LC viability or environmental issue."],
                ["Partial",
                 "Partially colonized — some sections clean, some not, "
                 "or grain did not fully colonize. Use with caution for inoculation."],
            ],
            col_widths=[3.5*cm, 12.7*cm],
        ),
        sp(8),
        callout(
            "The Grain Jars list page shows <b>clean rate</b> (clean jars ÷ total jars). "
            "A drop in clean rate across jars from the same LC lot is the earliest "
            "signal of a bad vendor lot — before any fruiting block data exists.",
            label="What to watch:", color=AMBER_BG, border=AMBER_BORDER
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 16. INTERACTIVE Q&A
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("16. Interactive Q&A"),
        rule(),
        p("The <b>Ask Claude</b> chat widget lets you query your cultivation data in plain "
          "English directly from any batch detail page. Instead of writing SQL or digging "
          "through report tables, you can ask questions like <i>\"What is the yield so far "
          "for this batch?\"</i> or <i>\"How does my contamination rate compare this month?\"</i> "
          "and get a concise, data-backed answer in seconds."),
        sp(8),

        h2("16.1  Opening the Chat Widget"),
        p("The widget is available on every <b>batch detail</b> page. Look for the green "
          "star button (&#9733;) fixed in the bottom-right corner of the screen. "
          "Click it to slide open the chat panel. The panel closes when you click the "
          "button again or press the &times; in the panel header."),
        sp(4),
        data_table(
            ["Feature", "Behaviour"],
            [
                ["Welcome message",
                 "The first time you open the panel it pre-loads three example questions "
                 "tailored to the batch you are viewing."],
                ["Send a question",
                 "Type in the text box and press Enter (or click Send). "
                 "Shift+Enter inserts a line break without sending."],
                ["Thinking indicator",
                 "A 'Thinking…' line appears while Claude queries the database. "
                 "Typical response time is 2–5 seconds."],
                ["Conversation history",
                 "Prior questions and answers stay visible in the panel for the "
                 "duration of your browser session. Claude uses up to the last 5 "
                 "exchanges as context for follow-up questions."],
                ["Availability",
                 "Only visible on batch detail pages — the button does not appear "
                 "on the dashboard, report, or other list pages."],
            ],
        ),
        sp(8),

        h2("16.2  How It Works"),
        p("Each question is sent to a small Claude AI model via the "
          "<b>POST /ask</b> endpoint. The model is given two tools:"),
        sp(4),
        *bullet([
            "<b>run_sql</b> — executes a read-only SELECT query against your local "
            "SQLite database and returns the results as tab-separated text.",
            "<b>get_schema</b> — returns the full table and column list so the model "
            "can construct accurate queries without guessing field names.",
        ]),
        sp(6),
        p("The model runs an internal reasoning loop (up to 5 tool calls per question) "
          "until it has enough data to compose a plain-English answer. "
          "Only SELECT and WITH queries are permitted — any attempt to run an "
          "INSERT, UPDATE, DELETE, or DROP is rejected before reaching the database."),
        sp(6),
        callout(
            "The chat widget requires an active ANTHROPIC_API_KEY environment variable. "
            "If the key is missing or invalid, the endpoint returns an error message "
            "inside the chat panel rather than crashing the page.",
            label="Requirement:", color=AMBER_BG, border=AMBER_BORDER,
        ),
        sp(6),
        p("<b>Example questions that work well:</b>"),
        *bullet([
            "\"What are the total flushes and yield for batch B-07?\"",
            "\"Which batch has the highest bio-efficiency this year?\"",
            "\"How many batches have been contaminated in the last 90 days?\"",
            "\"What is the average days-to-first-flush for Oyster batches?\"",
            "\"Show me the last 5 environment readings for my chamber.\"",
            "\"Which substrate recipe gives the best yield per kg dry weight?\"",
        ]),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 17. CLI REFERENCE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("17. Command-Line Interface (CLI)"),
        rule(),
        p("The CLI (<b>mushroom_tracker.py</b>) provides the same core functions as the web app "
          "from a terminal. It is useful for quick data entry when you do not want to open "
          "a browser, or for scripting."),
        sp(8),
        data_table(
            ["Command", "What It Does"],
            [
                ["python mushroom_tracker.py setup",
                 "Create a chamber or view existing one"],
                ["python mushroom_tracker.py status",
                 "Show the full dashboard: stats, batches, recent flushes"],
                ["python mushroom_tracker.py batch add",
                 "Add a new batch (interactive prompts)"],
                ["python mushroom_tracker.py batch list",
                 "List all batches with BE% and status"],
                ["python mushroom_tracker.py batch update <id>",
                 "Update a batch's lifecycle status"],
                ["python mushroom_tracker.py flush log <id>",
                 "Log a flush harvest for batch ID"],
                ["python mushroom_tracker.py flush list",
                 "List all flushes across all batches"],
                ["python mushroom_tracker.py env log",
                 "Log a new environment reading (interactive)"],
                ["python mushroom_tracker.py env history",
                 "View the last 20 environment readings"],
                ["python mushroom_tracker.py report",
                 "Print a performance summary with BE% ranking"],
            ],
            col_widths=[7.8*cm, 8.4*cm],
        ),
        sp(10),
        h3("Legacy Commands"),
        p("The old <b>block</b> and <b>harvest</b> commands still work as aliases "
          "for backwards compatibility:"),
        sp(4),
        data_table(
            ["Old Command", "Equivalent New Command"],
            [
                ["python mushroom_tracker.py block add",        "batch add"],
                ["python mushroom_tracker.py block list",       "batch list"],
                ["python mushroom_tracker.py block update <id>","batch update <id>"],
                ["python mushroom_tracker.py harvest log <id>", "flush log <id>"],
                ["python mushroom_tracker.py harvest list",     "flush list"],
            ],
            col_widths=[7.8*cm, 8.4*cm],
        ),
    ]

    story += [
        sp(10),
        h3("Example Morning Session"),
        code_block([
            "# Check what everything looks like",
            "python mushroom_tracker.py status",
            "",
            "# Log your morning environment reading",
            "python mushroom_tracker.py env log",
            "  Phase (fruiting/colonization/ambient): fruiting",
            "  Temperature F: 71.8",
            "  Humidity % RH: 89",
            "  CO2 ppm (Enter to skip): ",
            "  FAE fan cycles today: 4",
            "  Notes: misted twice this morning",
            "",
            "# After harvest: log a flush",
            "python mushroom_tracker.py flush log 1",
            "  Flush number [2]: ",
            "  Harvest date [2026-05-06]: ",
            "  Fresh weight grams: 210",
            "  Quality rating 1-5 (Enter to skip): 4",
            "  Notes: dense clusters, good caps",
        ]),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 18. GROWING REFERENCE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("18. Growing Reference"),
        rule(),
        h2("Optimal Fruiting Conditions by Species"),
        sp(4),
        callout(
            "When you create a new batch, set its <b>Target Temp</b> and <b>Target Humidity</b> "
            "fields to the values in this table for your species. "
            "These batch-level targets drive the dashed reference lines on the Environment History chart, "
            "so the chart always reflects what your current species actually needs.",
            label="Tip:", color=BLUE_BG, border=BLUE_BORDER
        ),
        sp(8),
        data_table(
            ["Species",        "Temp (F)", "Humidity", "FAE",     "Typical BE%",  "Notes"],
            [
                ["Blue Oyster",    "55-70",   "85-95%",  "High",    "75-150%",
                 "Best cold-weather oyster. Thrives in basement temps."],
                ["Pearl Oyster",   "65-75",   "85-95%",  "High",    "70-140%",
                 "Most forgiving oyster. Good starting species."],
                ["White Oyster",   "65-75",   "85-95%",  "High",    "70-140%",
                 "White strain of P. ostreatus. Nearly identical parameters to Pearl Oyster."],
                ["Pink Oyster",    "75-85",   "85-95%",  "High",    "60-120%",
                 "Tropical species. Needs warmth. Very fast colonizer."],
                ["Black Oyster",   "50-65",   "85-95%",  "High",    "70-130%",
                 "Dark strain, cold-fruiting like Blue Oyster. Slightly warmer range."],
                ["Elm Oyster",     "60-72",   "85-95%",  "High",    "40-80%",
                 "Slower colonizer than other oysters. Prefers slightly cooler fruiting temps."],
                ["Golden Oyster",  "65-75",   "85-95%",  "High",    "50-100%",
                 "Bright yellow caps. Fast colonizer. Releases spores heavily — harvest early."],
                ["King Oyster",    "55-65",   "85-95%",  "Low-Med", "70-90%",
                 "Thick stems are the main product. Low FAE produces longer, meatier stems."],
                ["Lions Mane",     "65-75",   "85-95%",  "Low-Med", "40-100%",
                 "Sensitive to CO2 -- causes elongated spines if too high."],
                ["Shiitake",       "55-75",   "80-90%",  "Medium",  "40-100%",
                 "Needs cold shocking (50F for 12-24h) to initiate."],
                ["Chestnut",       "55-65",   "85-95%",  "Medium",  "50-100%",
                 "Compact clusters. Cooler temps preferred."],
                ["Nameko",         "55-65",   "85-95%",  "Medium",  "40-80%",
                 "Glutinous cap surface. Fruiting similar to Shiitake. Cold-loving."],
                ["Pioppino",       "55-65",   "85-95%",  "Medium",  "30-70%",
                 "Slow colonizer. Dense clusters. Cooler fruiting preferred."],
                ["Maitake",        "55-65",   "85-95%",  "Medium",  "30-70%",
                 "Hen of the Woods. Long colonization. Best on oak supplemented blocks."],
                ["Bunashimeji",    "55-65",   "85-95%",  "Medium",  "30-60%",
                 "Beech mushroom. Very slow colonizer (45-90 days). Popular commercially."],
                ["Enoki",          "45-55",   "85-95%",  "Low",     "30-70%",
                 "Requires a cold chamber (45-55F) to fruit. Colonizes at room temp (65-75F)."],
                ["Reishi",         "75-85",   "85-95%",  "Low",     "10-40%",
                 "Low BE is expected. Value is in quality, not bulk."],
                ["Cordyceps",      "65-75",   "80-90%",  "Med",     "10-30%",
                 "Grows stroma (antlers), not caps. Substrate is typically brown rice or grain."],
                ["Turkey Tail",    "60-80",   "70-90%",  "Medium",  "5-20%",
                 "Medicinal; grown for polysaccharides, not culinary yield. Often log-cultivated."],
                ["Wine Cap",       "50-75",   "80-90%",  "Medium",  "30-80%",
                 "Typically outdoor garden-bed cultivation on wood chips or straw."],
            ],
            col_widths=[2.6*cm, 2.0*cm, 2.3*cm, 2.0*cm, 2.5*cm, 4.8*cm],
        ),
        sp(14),
        h2("Substrate Recipe Guide"),
        sp(4),
        data_table(
            ["Recipe Name",          "Composition",             "Best For",           "Notes"],
            [
                ["Master's Mix",     "HW 50% / Straw 50%",
                 "Oysters, Chestnut", "High BE. More water-holding than pure HW."],
                ["Standard HW Bran", "HW 85% / Bran 15%",
                 "Shiitake, Oysters", "Classic recipe. Keep bran under 20% to limit contam risk."],
                ["Pure Hardwood",    "HW 100%",
                 "Shiitake",         "Lower nitrogen but very stable. Longer colonization."],
                ["Straw Only",       "Straw 100%",
                 "Oysters (all)",    "Fastest colonization, easiest to source. Lower BE than HW."],
                ["Enriched HW",      "HW 80% / Bran 10% / Other 10%",
                 "Lions Mane",       "Higher nutrition for slower colonizers. More contam risk."],
            ],
            col_widths=[3.2*cm, 4*cm, 3.5*cm, 5.5*cm],
        ),
    ]

    story += [
        sp(14),
        h2("Shotgun Fruiting Chamber Quick Reference"),
        sp(6),
        data_table(
            ["Parameter",      "Typical Value",     "Notes"],
            [
                ["Container size",   "54-66 qt clear tote",
                 "Larger = more blocks but harder to maintain humidity"],
                ["Hole spacing",     "1 hole per sq inch",
                 "Use 1/4\" drill bit; cover exterior with dry perlite"],
                ["Perlite depth",    "4-6 inches",
                 "Saturate completely, let drain before filling"],
                ["Misting",          "2-4x per day",
                 "Mist the walls, not the blocks directly"],
                ["Fanning",          "2-4x per day",
                 "Wave the lid 10-15 times to exchange air"],
                ["Light",            "12h on / 12h off",
                 "Any indirect light source; not required for all species"],
                ["Temp range",       "65-75F",
                 "Basement temps are often ideal -- cool and stable"],
                ["Spawn rate",       "10-20% of dry substrate",
                 "Higher spawn rate = faster colonization but higher cost"],
            ],
            col_widths=[3.5*cm, 3.5*cm, 9.2*cm],
        ),
    ]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # 19. TIPS & TROUBLESHOOTING
    # ══════════════════════════════════════════════════════════════════════
    story += [
        h1("19. Tips & Troubleshooting"),
        rule(),
        h2("Improving Your BE%"),
        *bullet([
            "Start with a <b>pure hardwood + 10-15% bran</b> recipe as your baseline. "
            "It is well-documented and gives you a clean starting point.",
            "Keep spawn rate consistent (15% of dry substrate weight) so recipe changes "
            "are the only variable when you compare batches.",
            "Log every batch's dry weight before hydration -- BE% is meaningless without it.",
            "After 5+ batches, sort the Report page BE ranking to see which formulas "
            "outperform others for your specific species and conditions.",
        ]),
        sp(10),
        h2("Contamination"),
        *bullet([
            "<b>Green or black mold</b> (Trichoderma, Aspergillus) -- remove the batch "
            "from the chamber immediately in a sealed bag. Mark it Contaminated in the tracker "
            "and record the contamination type.",
            "Check the Report page after multiple contamination events -- if all affected "
            "batches share a spawn lot, the spawn is likely the source.",
            "Bran percentages above 20% dramatically increase contamination risk. "
            "Track this in your substrate composition to spot the pattern.",
        ]),
        sp(10),
        h2("No Pins Forming"),
        *bullet([
            "Check CO2 level if you have a meter -- elevated CO2 is the most common cause.",
            "Increase fanning or FAE fan cycles per day.",
            "Try a temperature drop of 5-10F for 12-24 hours (cold shock).",
            "Verify the block surface is moist, not dried out or waterlogged.",
            "For Shiitake: a deliberate cold shock at 50F for 12-24h almost always initiates pinning.",
        ]),
        sp(10),
        h2("Humidity Dropping Overnight"),
        *bullet([
            "Increase perlite depth to 5-6 inches.",
            "Add a second misting session before lights-out.",
            "Check for air leaks around the lid.",
            "Log your misting count in the environment form to correlate with humidity data.",
        ]),
        sp(10),
        h2("Data & Backup"),
        *bullet([
            "All production data lives in <b>mushroom_data.db</b> in your Python Scripts folder. "
            "The sandbox lives in <b>mushroom_data_sandbox.db</b> — both are independent SQLite files.",
            "Back up <b>mushroom_data.db</b> periodically — copy it to a USB drive or cloud folder.",
            "To start fresh: delete mushroom_data.db and run setup again. "
            "The sandbox can be wiped the same way without touching production.",
            "Use sandbox mode for any large-scale testing before applying changes to production data.",
            "The CLI and web app can both run simultaneously — they share the same file.",
            "To regenerate this guide after adding notes: run <b>python generate_guide.py</b>.",
        ]),
        sp(10),
        callout(
            "The tracker is a local application -- it stores nothing online and requires no account. "
            "Your data is entirely yours and stays on your machine.",
            label="Privacy:"
        ),
    ]

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"  PDF written to: {OUTPUT}")


if __name__ == "__main__":
    build()
