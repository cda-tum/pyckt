#!/usr/bin/env python3
"""Generate the pyckt progress slides (python-pptx).

Plain, content-focused deck for a 1:1 meeting — no heavy theming.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY = RGBColor(0x1F, 0x37, 0x5B)
BLUE = RGBColor(0x2E, 0x5E, 0xAA)
GREEN = RGBColor(0x1E, 0x7D, 0x3C)
AMBER = RGBColor(0xB5, 0x7A, 0x00)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xF2, 0xF5, 0xFA)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def add_slide():
    return prs.slides.add_slide(BLANK)


def textbox(slide, l, t, w, h):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    return tf


def set_run(p, text, size, bold=False, color=NAVY, italic=False):
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = "Calibri"
    return r


def band(slide, color=NAVY, h=1.1):
    """Top title band."""
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def title_on_band(slide, text, sub=None):
    band(slide)
    tf = textbox(slide, 0.55, 0.18, 12.2, 0.95)
    p = tf.paragraphs[0]
    set_run(p, text, 30, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    if sub:
        p2 = tf.add_paragraph()
        set_run(p2, sub, 14, color=RGBColor(0xD6, 0xE0, 0xF0))


def bullet(tf, text, level=0, size=18, bold=False, color=NAVY, space=8, first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.level = level
    p.space_after = Pt(space)
    prefix = "" if level == 0 else "– "
    set_run(p, ("• " if level == 0 else prefix), size, bold=bold, color=color)
    set_run(p, text, size, bold=bold, color=color)
    return p


# ── Slide 1 — Title ────────────────────────────────────────────────────
s = add_slide()
band(s, NAVY, h=7.5)  # full navy
tf = textbox(s, 0.8, 2.2, 11.7, 2.4)
p = tf.paragraphs[0]
set_run(p, "pyckt", 54, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
p2 = tf.add_paragraph()
set_run(p2, "Python re-implementation of the acst analog-circuit-synthesis tool", 24,
        color=RGBColor(0xD6, 0xE0, 0xF0))
p3 = tf.add_paragraph()
p3.space_before = Pt(24)
set_run(p3, "Progress report  ·  Firas  ·  2026-06-05", 18,
        color=RGBColor(0xAE, 0xC0, 0xDC))
p4 = tf.add_paragraph()
p4.space_before = Pt(40)
set_run(p4, "pyckt (Python):  github.com/cda-tum/pyckt", 15, color=RGBColor(0x9F, 0xB4, 0xD6))
p5 = tf.add_paragraph()
set_run(p5, "acst  (C++ reference):  github.com/inga000/acst", 15, color=RGBColor(0x9F, 0xB4, 0xD6))

# ── Slide 2 — Goal & approach ──────────────────────────────────────────
s = add_slide()
title_on_band(s, "Goal & approach")
tf = textbox(s, 0.7, 1.45, 12.0, 5.6)
bullet(tf, "Translate acst (~112,000 lines of C++) into a maintainable Python package",
       size=20, bold=True, first=True)
bullet(tf, "acst = analog circuit synthesis tool from TU München", level=1, size=17, color=GREY)
bullet(tf, "Reproduce the same six analysis modes …", size=20, bold=True)
bullet(tf, "structrec · partitioning · rulegen · automaticsizing · synthesis · toplibgen",
       level=1, size=17, color=GREY)
bullet(tf, "… and the same outputs, so Python can be validated against the original",
       size=20, bold=True)
bullet(tf, "acst is the reference: for any input, pyckt should match it", level=1, size=17, color=GREY)
bullet(tf, "Validation enabler: pyckt emits output in acst's exact XML schema",
       size=20, bold=True, color=BLUE)
bullet(tf, "(--output-format acst)  → outputs diffed tag-for-tag, not by eye",
       level=1, size=17, color=GREY)

# ── Slide 3 — Status at a glance ───────────────────────────────────────
s = add_slide()
title_on_band(s, "Status at a glance", "All six modes run end-to-end")
rows = [
    ("Mode", "Pipeline", "Output vs acst", "State"),
    ("structrec", "yes", "16/16 devices + full hierarchy match", "Done"),
    ("partitioning", "yes", "19/19 devices in same section", "Done"),
    ("rulegen", "yes", "10/10 items, 9/10 same level", "Done"),
    ("automaticsizing", "yes", "schema + perf models match; W/L tuning open", "Functional"),
    ("synthesis", "yes", "4,914 candidates ranked; netlists = placeholders", "Framework"),
    ("toplibgen", "yes", "1,725 topologies enumerated; netlists = placeholders", "Framework"),
]
table = s.shapes.add_table(len(rows), 4, Inches(0.55), Inches(1.55),
                           Inches(12.25), Inches(5.3)).table
table.columns[0].width = Inches(2.7)
table.columns[1].width = Inches(1.3)
table.columns[2].width = Inches(6.55)
table.columns[3].width = Inches(1.7)
state_color = {"Done": GREEN, "Functional": AMBER, "Framework": AMBER}
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        cell = table.cell(ri, ci)
        cell.margin_left = Inches(0.1); cell.margin_right = Inches(0.06)
        cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
        para = cell.text_frame.paragraphs[0]
        run = para.add_run(); run.text = val
        run.font.size = Pt(15 if ri else 15)
        run.font.name = "Calibri"
        if ri == 0:
            run.font.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
        else:
            cell.fill.solid()
            cell.fill.fore_color.rgb = LIGHT if ri % 2 else RGBColor(0xFF, 0xFF, 0xFF)
            if ci == 3:
                run.font.bold = True; run.font.color.rgb = state_color.get(val, GREY)
            elif ci == 0:
                run.font.bold = True; run.font.color.rgb = NAVY
            else:
                run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

# ── Slide 4 — Recognition modes match exactly ──────────────────────────
s = add_slide()
title_on_band(s, "Validation: recognition modes match acst", "Deterministic modes — exact agreement")
tf = textbox(s, 0.7, 1.5, 12.0, 5.4)
bullet(tf, "structrec — structure recognition", size=21, bold=True, color=GREEN, first=True)
bullet(tf, "16/16 devices to same structure; full composite hierarchy identical", level=1, size=17, color=GREY)
bullet(tf, "fixed this period: spurious LevelShifter + swapped diff-pair pins", level=1, size=15, color=GREY)
bullet(tf, "partitioning — circuit partitioning", size=21, bold=True, color=GREEN)
bullet(tf, "19/19 devices in same section (gm-path stages / bias / load / caps)", level=1, size=17, color=GREY)
bullet(tf, "was the biggest gap (1/6) → re-implemented to acst's stage logic → 19/19", level=1, size=15, color=GREY)
bullet(tf, "rulegen — sizing-rule library", size=21, bold=True, color=GREEN)
bullet(tf, "same pairLibrary artifact; 10/10 items, 9/10 at same hierarchy level", level=1, size=17, color=GREY)
tf2 = textbox(s, 0.7, 6.55, 12, 0.7)
p = tf2.paragraphs[0]
set_run(p, "→ See side-by-side XML in samples/structrec, samples/partitioning, samples/rulegen",
        14, italic=True, color=BLUE)

# ── Slide 5 — Sizing ───────────────────────────────────────────────────
s = add_slide()
title_on_band(s, "Validation: automatic sizing", "Output format & models match; optimiser tuning open")
tf = textbox(s, 0.7, 1.4, 6.0, 5.6)
bullet(tf, "Output schema matches acst", size=19, bold=True, color=GREEN, first=True)
bullet(tf, "ExpectedPerformance / Currents / Dimensions", level=1, size=15, color=GREY)
bullet(tf, "Performance models implemented", size=19, bold=True, color=GREEN)
bullet(tf, "Ft, slew rate, phase margin (were stubbed → 0)", level=1, size=15, color=GREY)
bullet(tf, "Produces a valid sized HSPICE netlist", size=19, bold=True, color=GREEN)
bullet(tf, "samples/sizing/sized_netlist_pyckt.hspice", level=1, size=15, color=GREY)
bullet(tf, "Open: solver under-sizes the design", size=19, bold=True, color=AMBER)
bullet(tf, "not yet at acst's operating point — main numeric item", level=1, size=15, color=GREY)
# small metric table
rows = [("Metric", "acst", "pyckt", "Δ"),
        ("Gain (dB)", "90.0", "91.3", "1.4%"),
        ("Slew (V/µs)", "22.5", "24.5", "8.8%"),
        ("Power (mW)", "6.12", "7.53", "23%"),
        ("Phase margin", "60.7", "87.2", "✗"),
        ("Transit f (MHz)", "6.93", "23.1", "✗"),
        ("Area (µm²)", "10868", "207", "✗")]
table = s.shapes.add_table(len(rows), 4, Inches(7.0), Inches(1.5),
                           Inches(5.8), Inches(4.7)).table
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        cell = table.cell(ri, ci)
        cell.margin_left = Inches(0.08); cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
        para = cell.text_frame.paragraphs[0]
        run = para.add_run(); run.text = val; run.font.size = Pt(15); run.font.name = "Calibri"
        if ri == 0:
            run.font.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT if ri % 2 else RGBColor(0xFF, 0xFF, 0xFF)
            if ci == 3:
                run.font.bold = True
                delta_color = {"1.4%": GREEN, "8.8%": GREEN, "23%": AMBER,
                               "✗": RGBColor(0xB0, 0x2A, 0x2A)}
                run.font.color.rgb = delta_color.get(val, GREY)
            elif ci == 0:
                run.font.color.rgb = NAVY; run.font.bold = True
            else:
                run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

# ── Slide 6 — Synthesis / toplibgen ────────────────────────────────────
s = add_slide()
title_on_band(s, "Synthesis & topology generation", "Enumeration + ranking framework complete")
tf = textbox(s, 0.7, 1.55, 12.0, 5.2)
bullet(tf, "synthesis — enumerate, size, rank candidate topologies", size=20, bold=True, first=True)
bullet(tf, "4,914 candidates ranked (rank / score / gain / power / area / Ft)", level=1, size=17, color=GREY)
bullet(tf, "samples/synthesis/synthesis_ranking_pyckt.json", level=1, size=14, color=BLUE)
bullet(tf, "toplibgen — enumerate the op-amp topology library", size=20, bold=True)
bullet(tf, "1,725 topologies (133 one-stage + 1,592 two-stage), each with metadata", level=1, size=17, color=GREY)
bullet(tf, "Framework done; per-topology netlist bodies still placeholders (next phase)",
       size=18, bold=True, color=AMBER)
bullet(tf, "acst's generators run minutes–hours → direct output diff deferred until offline run",
       size=16, color=GREY)

# ── Slide 7 — Recent progress + next steps ─────────────────────────────
s = add_slide()
title_on_band(s, "Recent progress  &  next steps")
tf = textbox(s, 0.65, 1.45, 6.1, 5.6)
bullet(tf, "Done this period", size=20, bold=True, color=GREEN, first=True)
bullet(tf, "acst-compatible output writer (all modes)", level=1, size=16, color=GREY)
bullet(tf, "partitioning re-implemented → 1/6 → 19/19", level=1, size=16, color=GREY)
bullet(tf, "structrec hierarchy + pin-label fixes → 16/16", level=1, size=16, color=GREY)
bullet(tf, "sizing performance models implemented", level=1, size=16, color=GREY)
bullet(tf, "parser robustness fixes", level=1, size=16, color=GREY)
tf2 = textbox(s, 6.95, 1.45, 5.9, 5.6)
bullet(tf2, "Next", size=20, bold=True, color=BLUE, first=True)
bullet(tf2, "tune sizing solver to acst's operating point", level=1, size=16, color=GREY)
bullet(tf2, "real synthesis / toplibgen netlist bodies", level=1, size=16, color=GREY)
bullet(tf2, "reconcile rulegen level + persistence", level=1, size=16, color=GREY)
bullet(tf2, "derive partitioning nets from structure tree", level=1, size=16, color=GREY)
bullet(tf2, "run acst to completion → validate synth/toplibgen", level=1, size=16, color=GREY)

prs.save("/home/jrad/report/slides/pyckt_progress.pptx")
print("Saved pyckt_progress.pptx with", len(prs.slides._sldIdLst), "slides")
