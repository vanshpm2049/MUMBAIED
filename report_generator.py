import io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Palette ──────────────────────────────────────────────────────────────────
DARK_BG   = colors.HexColor("#0d1117")
CARD_BG   = colors.HexColor("#161b22")
ACCENT    = colors.HexColor("#238636")
ACCENT2   = colors.HexColor("#1f6feb")
TEXT_MAIN = colors.HexColor("#e6edf3")
TEXT_MUTE = colors.HexColor("#8b949e")
BORDER    = colors.HexColor("#30363d")
ORANGE    = colors.HexColor("#d29922")
RED       = colors.HexColor("#da3633")

W, H = A4  # 210 × 297 mm

# ── Styles ────────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    def ps(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=base[parent], **kw)
    return {
        "title":    ps("title",    fontSize=20, textColor=TEXT_MAIN,  alignment=TA_LEFT,   leading=24, fontName="Helvetica-Bold"),
        "subtitle": ps("subtitle", fontSize=11, textColor=TEXT_MUTE,  alignment=TA_LEFT,   leading=14),
        "section":  ps("section",  fontSize=13, textColor=ACCENT2,    alignment=TA_LEFT,   leading=18, fontName="Helvetica-Bold", spaceAfter=4),
        "kpi_val":  ps("kpi_val",  fontSize=22, textColor=TEXT_MAIN,  alignment=TA_CENTER, leading=26, fontName="Helvetica-Bold"),
        "kpi_lbl":  ps("kpi_lbl",  fontSize=8,  textColor=TEXT_MUTE,  alignment=TA_CENTER, leading=10),
        "body":     ps("body",     fontSize=9,  textColor=TEXT_MAIN,  alignment=TA_LEFT,   leading=13),
        "footer":   ps("footer",   fontSize=7,  textColor=TEXT_MUTE,  alignment=TA_CENTER, leading=9),
        "tag":      ps("tag",      fontSize=8,  textColor=ACCENT,     alignment=TA_CENTER, leading=10, fontName="Helvetica-Bold"),
    }

# ── Helpers ───────────────────────────────────────────────────────────────────
def _turnout_color(t):
    if t > 70:   return "#04ff00"
    elif t > 60: return "#6aff00"
    elif t > 55: return "#ffea00"
    elif t > 50: return "#ffa600"
    elif t > 45: return "#ff6f00"
    else:        return "#ff4d4d"

def _bar_chart(labels, values, title, highlight_label=None, figsize=(6.5, 2.8)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    bar_colors = []
    for l, v in zip(labels, values):
        if l == highlight_label:
            bar_colors.append("#1f6feb")
        else:
            bar_colors.append(_turnout_color(v * 100 if v <= 1 else v))

    bars = ax.barh(labels, values, color=bar_colors, height=0.55, edgecolor="none")

    for bar, val in zip(bars, values):
        display = f"{val*100:.1f}%" if val <= 1 else f"{val:.1f}%"
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                display, va="center", ha="left", color="#e6edf3", fontsize=7.5)

    ax.set_xlim(0, (max(values) * 1.18) if values else 1)
    ax.set_xlabel("Voter Turnout (%)", color="#8b949e", fontsize=8)
    ax.set_title(title, color="#e6edf3", fontsize=9, pad=8, fontweight="bold")
    ax.tick_params(colors="#8b949e", labelsize=7.5)
    ax.xaxis.label.set_color("#8b949e")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.grid(axis="x", color="#30363d", linewidth=0.5, linestyle="--")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf

def _gauge_chart(value, figsize=(2.2, 2.2)):
    """Semi-circle gauge for turnout."""
    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(aspect="equal"))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    theta = 3.14159 * (1 - value / 100)
    bg   = mpatches.Wedge((0.5, 0.3), 0.38, 0, 180, width=0.12,
                           facecolor="#30363d", transform=ax.transAxes)
    fill = mpatches.Wedge((0.5, 0.3), 0.38, 0, 180 * (value / 100), width=0.12,
                           facecolor=_turnout_color(value), transform=ax.transAxes)
    ax.add_patch(bg)
    ax.add_patch(fill)
    ax.text(0.5, 0.28, f"{value:.1f}%", transform=ax.transAxes,
            ha="center", va="center", fontsize=13, fontweight="bold",
            color="#e6edf3")
    ax.text(0.5, 0.08, "Turnout", transform=ax.transAxes,
            ha="center", va="center", fontsize=7, color="#8b949e")
    ax.axis("off")

    buf = io.BytesIO()
    plt.tight_layout(pad=0)
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#0d1117")
    plt.close(fig)
    buf.seek(0)
    return buf

def _kpi_table(kpis, styles):
    """Row of KPI cards: [(label, value), ...]"""
    n = len(kpis)
    col_w = (W - 28*mm) / n

    data = [[Paragraph(v, styles["kpi_val"]) for _, v in kpis],
            [Paragraph(l, styles["kpi_lbl"]) for l, _ in kpis]]

    t = Table(data, colWidths=[col_w]*n, rowHeights=[28, 14])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), CARD_BG),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [CARD_BG, CARD_BG]),
        ("BOX",         (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",   (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING",  (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING",(0,0), (-1,-1), 4),
    ]))
    return t

def _page_header(story, title_text, subtitle_text, styles):
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT2, spaceAfter=6))
    story.append(Paragraph(title_text, styles["title"]))
    story.append(Paragraph(subtitle_text, styles["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=10))

def _page_footer(story, styles):
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=4, spaceAfter=4))
    story.append(Paragraph("Maharashtra Election Intelligence Dashboard  •  Confidential", styles["footer"]))

# ── AC Fact Sheet ─────────────────────────────────────────────────────────────
def generate_ac_report(ac_df: pd.DataFrame, pc_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = _styles()
    story  = []

    ac_df = ac_df.copy()
    ac_df["ac_name_clean"] = ac_df["ac_name"].str.title()

    # Normalize turnout to percentage
    if ac_df["turnout_percentage"].max() <= 1:
        ac_df["turnout_pct"] = ac_df["turnout_percentage"] * 100
    else:
        ac_df["turnout_pct"] = ac_df["turnout_percentage"]

    avg_turnout = ac_df["turnout_pct"].mean()
    max_row     = ac_df.loc[ac_df["turnout_pct"].idxmax()]
    min_row     = ac_df.loc[ac_df["turnout_pct"].idxmin()]

    # ── Cover summary page ──
    _page_header(story,
                 "Assembly Constituency Report",
                 "Maharashtra Assembly Elections 2024  •  All Constituencies",
                 styles)

    kpis = [
        ("Total ACs",         str(len(ac_df))),
        ("Avg Turnout",       f"{avg_turnout:.1f}%"),
        ("Highest",           f"{max_row['ac_name_clean']}\n{max_row['turnout_pct']:.1f}%"),
        ("Lowest",            f"{min_row['ac_name_clean']}\n{min_row['turnout_pct']:.1f}%"),
    ]
    story.append(_kpi_table(kpis, styles))
    story.append(Spacer(1, 10))

    # Overall bar chart
    story.append(Paragraph("All Constituencies — Voter Turnout", styles["section"]))
    sorted_ac = ac_df.sort_values("turnout_pct", ascending=True)
    chart_buf = _bar_chart(
        sorted_ac["ac_name_clean"].tolist(),
        sorted_ac["turnout_pct"].tolist(),
        "Assembly Constituencies by Turnout (%)",
        figsize=(6.8, max(3.5, len(ac_df) * 0.22))
    )
    story.append(Image(chart_buf, width=W - 28*mm, height=min(180*mm, max(90*mm, len(ac_df)*5.5))))
    _page_footer(story, styles)
    story.append(PageBreak())

    # ── One page per AC ──
    for _, row in ac_df.iterrows():
        t_pct   = row["turnout_pct"]
        ac_name = row["ac_name_clean"]

        _page_header(story,
                     f"Assembly Constituency: {ac_name}",
                     f"AC No. {int(row['ac_no'])}  •  Maharashtra Assembly Elections 2024",
                     styles)

        # KPIs
        total_electors = int(row.get("electors_total", 0))
        total_voters   = int(row.get("voters_total", 0))
        male_e   = int(row.get("electors_male", 0))
        female_e = int(row.get("electors_female", 0))
        male_v   = int(row.get("voters_male", 0))
        female_v = int(row.get("voters_female", 0))

        kpis = [
            ("Total Electors",  f"{total_electors:,}"),
            ("Votes Polled",    f"{total_voters:,}"),
            ("Turnout",         f"{t_pct:.1f}%"),
            ("Male Turnout",    f"{(male_v/male_e*100) if male_e else 0:.1f}%"),
            ("Female Turnout",  f"{(female_v/female_e*100) if female_e else 0:.1f}%"),
        ]
        story.append(_kpi_table(kpis, styles))
        story.append(Spacer(1, 10))

        # Gauge + context bar side by side
        story.append(Paragraph("Turnout Overview", styles["section"]))

        gauge_buf = _gauge_chart(t_pct, figsize=(2.4, 2.0))
        gauge_img = Image(gauge_buf, width=55*mm, height=46*mm)

        # Context: this AC vs avg
        ctx_labels = ["State Avg", ac_name]
        ctx_values = [avg_turnout, t_pct]
        ctx_buf    = _bar_chart(ctx_labels, ctx_values,
                                "vs. State Average", highlight_label=ac_name,
                                figsize=(4.2, 1.6))
        ctx_img = Image(ctx_buf, width=W - 28*mm - 60*mm, height=46*mm)

        side = Table([[gauge_img, ctx_img]],
                     colWidths=[60*mm, W - 28*mm - 60*mm])
        side.setStyle(TableStyle([
            ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(side)
        story.append(Spacer(1, 8))

        # Voter breakdown table
        story.append(Paragraph("Voter Breakdown", styles["section"]))
        tbl_data = [
            [Paragraph("Category",       styles["body"]),
             Paragraph("Electors",       styles["body"]),
             Paragraph("Votes Polled",   styles["body"]),
             Paragraph("Turnout %",      styles["body"])],
            [Paragraph("Male",           styles["body"]),
             Paragraph(f"{male_e:,}",   styles["body"]),
             Paragraph(f"{male_v:,}",   styles["body"]),
             Paragraph(f"{(male_v/male_e*100) if male_e else 0:.1f}%", styles["body"])],
            [Paragraph("Female",         styles["body"]),
             Paragraph(f"{female_e:,}", styles["body"]),
             Paragraph(f"{female_v:,}", styles["body"]),
             Paragraph(f"{(female_v/female_e*100) if female_e else 0:.1f}%", styles["body"])],
            [Paragraph("<b>Total</b>",   styles["body"]),
             Paragraph(f"<b>{total_electors:,}</b>", styles["body"]),
             Paragraph(f"<b>{total_voters:,}</b>",   styles["body"]),
             Paragraph(f"<b>{t_pct:.1f}%</b>",       styles["body"])],
        ]
        col_w = (W - 28*mm) / 4
        tbl = Table(tbl_data, colWidths=[col_w]*4, rowHeights=16)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  ACCENT2),
            ("BACKGROUND",    (0,1), (-1,-2), CARD_BG),
            ("BACKGROUND",    (0,-1),(-1,-1), colors.HexColor("#1c2128")),
            ("TEXTCOLOR",     (0,0), (-1,0),  TEXT_MAIN),
            ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ]))
        story.append(tbl)

        _page_footer(story, styles)
        story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()


# ── PC Fact Sheet ─────────────────────────────────────────────────────────────
def generate_pc_report(pc_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = _styles()
    story  = []

    pc_df = pc_df.copy()

    # Ffill merged cells
    for col in pc_df.columns:
        key = col.lower().replace(".", "").replace(" ", "_")
        if any(k in key for k in ["pc_no", "pc_name", "district_no", "district_name"]):
            pc_df[col] = pc_df[col].ffill()

    pc_name_col = next((c for c in pc_df.columns if "pc" in c.lower() and "name" in c.lower()), None)
    ac_name_col = next((c for c in pc_df.columns if "ac" in c.lower() and "name" in c.lower()), None)
    turnout_col = next((c for c in pc_df.columns if "turnout" in c.lower()), None)
    male_col    = next((c for c in pc_df.columns if c.lower() == "male"), None)
    female_col  = next((c for c in pc_df.columns if c.lower() == "female"), None)
    total_col   = next((c for c in pc_df.columns if c.lower() == "total"), None)
    polled_col  = next((c for c in pc_df.columns if "polled" in c.lower() or c.lower() == "votes polled"), None)

    pc_groups = pc_df.groupby(pc_name_col)
    avg_pc_turnout = pc_df[turnout_col].mean()

    # ── Cover page ──
    _page_header(story,
                 "Parliamentary Constituency Report",
                 "Maharashtra General Elections 2024  •  All Constituencies",
                 styles)

    pc_summary = pc_groups[turnout_col].mean().reset_index()
    pc_summary.columns = ["PC", "Turnout"]
    max_pc = pc_summary.loc[pc_summary["Turnout"].idxmax()]
    min_pc = pc_summary.loc[pc_summary["Turnout"].idxmin()]

    kpis = [
        ("Total PCs",     str(pc_summary.shape[0])),
        ("Total ACs",     str(len(pc_df))),
        ("Avg Turnout",   f"{avg_pc_turnout:.1f}%"),
        ("Highest PC",    f"{max_pc['PC']}\n{max_pc['Turnout']:.1f}%"),
        ("Lowest PC",     f"{min_pc['PC']}\n{min_pc['Turnout']:.1f}%"),
    ]
    story.append(_kpi_table(kpis, styles))
    story.append(Spacer(1, 10))

    story.append(Paragraph("All Parliamentary Constituencies — Avg Turnout", styles["section"]))
    sorted_pc = pc_summary.sort_values("Turnout", ascending=True)
    chart_buf = _bar_chart(
        sorted_pc["PC"].tolist(),
        sorted_pc["Turnout"].tolist(),
        "PC-wise Average Voter Turnout (%)",
        figsize=(6.8, max(3.0, len(pc_summary) * 0.38))
    )
    story.append(Image(chart_buf, width=W - 28*mm, height=min(160*mm, max(80*mm, len(pc_summary)*14))))
    _page_footer(story, styles)
    story.append(PageBreak())

    # ── One page per PC ──
    for pc_name, group in pc_groups:
        group = group.copy()
        avg_t = group[turnout_col].mean()

        _page_header(story,
                     f"Parliamentary Constituency: {pc_name}",
                     f"Maharashtra General Elections 2024  •  {len(group)} Assembly Segments",
                     styles)

        total_electors = int(group[total_col].sum()) if total_col else 0
        total_polled   = int(group[polled_col].sum()) if polled_col else 0
        total_male     = int(group[male_col].sum())   if male_col else 0
        total_female   = int(group[female_col].sum()) if female_col else 0

        kpis = [
            ("Assembly Segments", str(len(group))),
            ("Total Electors",    f"{total_electors:,}"),
            ("Votes Polled",      f"{total_polled:,}"),
            ("Avg Turnout",       f"{avg_t:.1f}%"),
        ]
        story.append(_kpi_table(kpis, styles))
        story.append(Spacer(1, 10))

        # Gauge + vs avg
        story.append(Paragraph("Turnout Overview", styles["section"]))
        gauge_buf = _gauge_chart(avg_t, figsize=(2.4, 2.0))
        gauge_img = Image(gauge_buf, width=55*mm, height=46*mm)

        ctx_labels = ["State Avg", pc_name]
        ctx_values = [avg_pc_turnout, avg_t]
        ctx_buf    = _bar_chart(ctx_labels, ctx_values,
                                "vs. State Average", highlight_label=pc_name,
                                figsize=(4.2, 1.6))
        ctx_img = Image(ctx_buf, width=W - 28*mm - 60*mm, height=46*mm)

        side = Table([[gauge_img, ctx_img]],
                     colWidths=[60*mm, W - 28*mm - 60*mm])
        side.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(side)
        story.append(Spacer(1, 8))

        # AC breakdown bar chart
        story.append(Paragraph("Assembly Segment Turnout Breakdown", styles["section"]))
        ac_sorted = group.sort_values(turnout_col, ascending=True)
        ac_chart  = _bar_chart(
            ac_sorted[ac_name_col].astype(str).tolist(),
            ac_sorted[turnout_col].tolist(),
            f"Segment-wise Turnout — {pc_name}",
            figsize=(6.5, max(2.4, len(group) * 0.36))
        )
        chart_h = min(90*mm, max(55*mm, len(group) * 13))
        story.append(Image(ac_chart, width=W - 28*mm, height=chart_h))
        story.append(Spacer(1, 6))

        # AC table
        story.append(Paragraph("Segment Details", styles["section"]))
        headers = ["AC Name", "Total Electors", "Votes Polled", "Turnout %"]
        tbl_data = [[Paragraph(h, styles["body"]) for h in headers]]
        for _, r in group.iterrows():
            tbl_data.append([
                Paragraph(str(r[ac_name_col]), styles["body"]),
                Paragraph(f"{int(r[total_col]):,}" if total_col else "—", styles["body"]),
                Paragraph(f"{int(r[polled_col]):,}" if polled_col else "—", styles["body"]),
                Paragraph(f"{r[turnout_col]:.1f}%", styles["body"]),
            ])

        col_w = (W - 28*mm) / 4
        tbl = Table(tbl_data, colWidths=[col_w*1.4, col_w*0.9, col_w*0.9, col_w*0.8],
                    rowHeights=14)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  ACCENT2),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [CARD_BG, colors.HexColor("#1c2128")]),
            ("TEXTCOLOR",     (0,0), (-1,0),  TEXT_MAIN),
            ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ]))
        story.append(tbl)

        _page_footer(story, styles)
        story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()


# ── AC Deep Dive Fact Sheet ────────────────────────────────────────────────────
def generate_ac_deepdive_report(merged_df: pd.DataFrame, single_ac: str = None) -> bytes:
    """
    merged_df must have columns:
      ac_name_clean, assembly_turnout, general_turnout, turnout_diff,
      electors_total, electors_male, electors_female,
      voters_total, voters_male, voters_female,
      total_electors_pc, votes_polled, nota, postal, pc_name
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = _styles()
    story  = []

    df = merged_df.copy().reset_index(drop=True)

    def safe_int(val):
        try:
            return int(val) if pd.notna(val) else 0
        except:
            return 0

    def diff_label(d):
        return f"+{d:.2f}%" if d >= 0 else f"{d:.2f}%"

    # ── Swing bar chart (all ACs) ──────────────────────────────────────────
    def _swing_chart(data, highlight=None):
        data = data.sort_values("turnout_diff", ascending=True)
        fig, ax = plt.subplots(figsize=(6.8, max(3.2, len(data) * 0.22)))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        bar_colors = []
        for _, r in data.iterrows():
            if r["ac_name_clean"] == highlight:
                bar_colors.append("#1f6feb")
            elif r["turnout_diff"] >= 0:
                bar_colors.append("#238636")
            else:
                bar_colors.append("#da3633")

        bars = ax.barh(data["ac_name_clean"], data["turnout_diff"],
                       color=bar_colors, height=0.55, edgecolor="none")
        for bar, (_, r) in zip(bars, data.iterrows()):
            w = bar.get_width()
            ax.text(w + (0.15 if w >= 0 else -0.15),
                    bar.get_y() + bar.get_height() / 2,
                    diff_label(r["turnout_diff"]),
                    va="center", ha="left" if w >= 0 else "right",
                    color="#e6edf3", fontsize=7)

        ax.axvline(0, color="#8b949e", linewidth=0.8, linestyle="--")
        ax.set_xlabel("Swing % (General − Assembly)", color="#8b949e", fontsize=8)
        ax.set_title("Turnout Swing per AC", color="#e6edf3", fontsize=9,
                     fontweight="bold", pad=8)
        ax.tick_params(colors="#8b949e", labelsize=7)
        for sp in ax.spines.values():
            sp.set_edgecolor("#30363d")
        ax.grid(axis="x", color="#30363d", linewidth=0.5, linestyle="--")

        b = io.BytesIO()
        plt.tight_layout()
        plt.savefig(b, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        b.seek(0)
        return b

    # ── Comparison bar (two bars) ──────────────────────────────────────────
    def _cmp_chart(asm_t, gen_t, ac_name):
        fig, ax = plt.subplots(figsize=(3.8, 1.8))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")
        bars = ax.bar(["Assembly 2024", "General 2024"], [asm_t, gen_t],
                      color=["#1f6feb", "#238636"], width=0.45, edgecolor="none")
        for b, v in zip(bars, [asm_t, gen_t]):
            ax.text(b.get_x() + b.get_width()/2, v + 0.5, f"{v:.1f}%",
                    ha="center", va="bottom", color="#e6edf3", fontsize=8,
                    fontweight="bold")
        ax.set_ylim(0, max(asm_t, gen_t) * 1.2)
        ax.set_title(f"Turnout — {ac_name}", color="#e6edf3", fontsize=8,
                     fontweight="bold", pad=6)
        ax.tick_params(colors="#8b949e", labelsize=7.5)
        for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
        ax.grid(axis="y", color="#30363d", linewidth=0.5, linestyle="--")
        b2 = io.BytesIO()
        plt.tight_layout()
        plt.savefig(b2, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        b2.seek(0)
        return b2

    # ── Gender pie ─────────────────────────────────────────────────────────
    def _gender_chart(male_v, female_v):
        fig, ax = plt.subplots(figsize=(2.6, 2.0))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        vals = [male_v, female_v]
        clrs = ["#1f6feb", "#d29922"]
        lbls = [f"Male\n{male_v:,}", f"Female\n{female_v:,}"]
        wedges, texts, autotexts = ax.pie(
            vals, labels=lbls, colors=clrs,
            autopct="%1.1f%%", startangle=90,
            textprops={"color": "#e6edf3", "fontsize": 7},
            wedgeprops={"width": 0.55}
        )
        for at in autotexts:
            at.set_fontsize(7)
            at.set_color("#0d1117")
        ax.set_title("Gender Split\n(Assembly Voters)", color="#e6edf3",
                     fontsize=7.5, fontweight="bold", pad=4)
        b3 = io.BytesIO()
        plt.tight_layout()
        plt.savefig(b3, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        b3.seek(0)
        return b3

    # ════════════════════════════════════════════════════════════════════════
    # COVER PAGE — summary of all ACs
    # ════════════════════════════════════════════════════════════════════════
    title_suffix = f"— {single_ac}" if single_ac else "— All Constituencies"
    _page_header(story,
                 f"AC Deep Dive Fact Sheet {title_suffix}",
                 "Maharashtra Elections 2024  •  Assembly vs General Election Comparison",
                 styles)

    avg_asm = df["assembly_turnout"].mean()
    avg_gen = df["general_turnout"].mean()
    avg_diff = df["turnout_diff"].mean()
    best_swing = df.loc[df["turnout_diff"].idxmax()]
    worst_swing = df.loc[df["turnout_diff"].idxmin()]

    kpis = [
        ("ACs Covered",        str(len(df))),
        ("Avg Assembly Turnout", f"{avg_asm:.1f}%"),
        ("Avg General Turnout",  f"{avg_gen:.1f}%"),
        ("Avg Swing",            diff_label(avg_diff)),
        ("Best Swing",           f"{best_swing['ac_name_clean']}\n{diff_label(best_swing['turnout_diff'])}"),
        ("Worst Swing",          f"{worst_swing['ac_name_clean']}\n{diff_label(worst_swing['turnout_diff'])}"),
    ]
    story.append(_kpi_table(kpis, styles))
    story.append(Spacer(1, 10))

    # Swing chart covering all ACs
    story.append(Paragraph("Turnout Swing Overview (General − Assembly)", styles["section"]))
    swing_buf = _swing_chart(df, highlight=single_ac)
    chart_h = min(180*mm, max(80*mm, len(df) * 5.8))
    story.append(Image(swing_buf, width=W - 28*mm, height=chart_h))

    # Summary table
    story.append(Spacer(1, 8))
    story.append(Paragraph("Summary Table", styles["section"]))
    hdr = ["AC Name", "PC Name", "Assembly %", "General %", "Swing"]
    tbl_data = [[Paragraph(h, styles["body"]) for h in hdr]]
    for _, r in df.sort_values("turnout_diff", ascending=False).iterrows():
        tbl_data.append([
            Paragraph(str(r["ac_name_clean"]), styles["body"]),
            Paragraph(str(r.get("pc_name", "—")), styles["body"]),
            Paragraph(f"{r['assembly_turnout']:.2f}%", styles["body"]),
            Paragraph(f"{r['general_turnout']:.2f}%", styles["body"]),
            Paragraph(diff_label(r["turnout_diff"]), styles["body"]),
        ])
    cw = (W - 28*mm)
    tbl = Table(tbl_data,
                colWidths=[cw*0.28, cw*0.27, cw*0.16, cw*0.16, cw*0.13],
                rowHeights=13)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  ACCENT2),
        ("ROWBACKGROUNDS",(0,1),  (-1,-1), [CARD_BG, colors.HexColor("#1c2128")]),
        ("TEXTCOLOR",     (0,0),  (-1,0),  TEXT_MAIN),
        ("GRID",          (0,0),  (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0),  (-1,-1), 3),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 3),
        ("LEFTPADDING",   (0,0),  (-1,-1), 5),
    ]))
    story.append(tbl)
    _page_footer(story, styles)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # ONE PAGE PER AC
    # ════════════════════════════════════════════════════════════════════════
    for _, row in df.iterrows():
        ac_name  = row["ac_name_clean"]
        asm_t    = row["assembly_turnout"]
        gen_t    = row["general_turnout"]
        diff     = row["turnout_diff"]

        _page_header(story,
                     f"AC Deep Dive: {ac_name}",
                     f"PC: {row.get('pc_name', '—')}  •  Maharashtra Elections 2024",
                     styles)

        # KPI row
        kpis = [
            ("Assembly Turnout",    f"{asm_t:.2f}%"),
            ("General Turnout",     f"{gen_t:.2f}%"),
            ("Swing",               diff_label(diff)),
            ("Total Electors (Asm)",f"{safe_int(row.get('electors_total')):,}"),
            ("Votes Polled (Asm)",  f"{safe_int(row.get('voters_total')):,}"),
        ]
        story.append(_kpi_table(kpis, styles))
        story.append(Spacer(1, 8))

        # Charts row: comparison bar | gender pie | gauge
        story.append(Paragraph("Turnout & Voter Profile", styles["section"]))

        cmp_buf    = _cmp_chart(asm_t, gen_t, ac_name)
        gender_buf = _gender_chart(safe_int(row.get("voters_male")),
                                   safe_int(row.get("voters_female")))
        gauge_buf  = _gauge_chart(gen_t, figsize=(2.2, 1.9))

        cmp_img    = Image(cmp_buf,    width=72*mm,  height=46*mm)
        gender_img = Image(gender_buf, width=58*mm,  height=46*mm)
        gauge_img  = Image(gauge_buf,  width=48*mm,  height=46*mm)

        charts_tbl = Table([[cmp_img, gender_img, gauge_img]],
                           colWidths=[72*mm, 58*mm, 48*mm])
        charts_tbl.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(charts_tbl)
        story.append(Spacer(1, 8))

        # Detailed breakdown table
        story.append(Paragraph("Detailed Statistics", styles["section"]))
        rows_data = [
            ["Metric", "Assembly Election", "General Election"],
            ["Total Electors",
             f"{safe_int(row.get('electors_total')):,}",
             f"{safe_int(row.get('total_electors_pc')):,}"],
            ["Male Electors",
             f"{safe_int(row.get('electors_male')):,}", "—"],
            ["Female Electors",
             f"{safe_int(row.get('electors_female')):,}", "—"],
            ["Votes Polled",
             f"{safe_int(row.get('voters_total')):,}",
             f"{safe_int(row.get('votes_polled')):,}"],
            ["Male Votes Polled",
             f"{safe_int(row.get('voters_male')):,}", "—"],
            ["Female Votes Polled",
             f"{safe_int(row.get('voters_female')):,}", "—"],
            ["NOTA",          "—", f"{safe_int(row.get('nota')):,}"],
            ["Postal Ballots","—", f"{safe_int(row.get('postal')):,}"],
            ["Voter Turnout",
             f"{asm_t:.2f}%", f"{gen_t:.2f}%"],
            ["Swing (Gen − Asm)", "—", diff_label(diff)],
        ]
        col_w = (W - 28*mm) / 3
        tbl = Table(
            [[Paragraph(str(c), styles["body"]) for c in r] for r in rows_data],
            colWidths=[col_w, col_w, col_w],
            rowHeights=14
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),  (-1,0),  ACCENT2),
            ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#1c2128")),
            ("ROWBACKGROUNDS",(0,1),  (-1,-2), [CARD_BG, colors.HexColor("#1c2128")]),
            ("TEXTCOLOR",     (0,0),  (-1,0),  TEXT_MAIN),
            ("GRID",          (0,0),  (-1,-1), 0.4, BORDER),
            ("TOPPADDING",    (0,0),  (-1,-1), 3),
            ("BOTTOMPADDING", (0,0),  (-1,-1), 3),
            ("LEFTPADDING",   (0,0),  (-1,-1), 6),
            ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ]))
        story.append(tbl)
        _page_footer(story, styles)
        story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
