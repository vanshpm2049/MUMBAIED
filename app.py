import streamlit as st
import pandas as pd
import json
import folium
import plotly.express as px
from streamlit_folium import st_folium
from folium.features import GeoJsonTooltip
from report_generator import generate_ac_report, generate_pc_report

st.set_page_config(
    page_title="Maharashtra Election Intelligence Dashboard",
    layout="wide"
)

# ---------------- LOAD CSS ----------------
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------- LOAD DATA ----------------
ac = pd.read_csv("data/AC_clean.csv")
pc = pd.read_csv("data/PC_clean.csv")
# Forward-fill merged cell columns (PC No., PC Name, District No., District Name)
_ffill_cols = [c for c in pc.columns if any(k in c.lower().replace('.','').replace(' ','_') for k in ['pc_no', 'pc_name', 'district_no', 'district_name'])]
pc[_ffill_cols] = pc[_ffill_cols].ffill()

with open("data/maharashtra_geo.json") as f:
    geojson = json.load(f)

ac["ac_no"] = ac["ac_no"].astype(str)

# ---------------- SIDEBAR ----------------
st.sidebar.title("Election Filters")

view_type = st.sidebar.radio(
    "Select View",
    ["Assembly Election", "Parliamentary Election", "Constituency Deep Dive", "AC vs PC Comparison"]
)

map_location = [19.1000, 72.8800]
map_zoom     = 11

# ---------------- PAGE TITLE ----------------
st.title("🗳 Maharashtra Election Intelligence Dashboard")

# =========================================================
# ASSEMBLY VIEW
# =========================================================
if view_type == "Assembly Election":

    districts = ["All"] + sorted(
        [str(x) for x in pc["district_name"].dropna().unique()]
    )

    selected_district = st.sidebar.selectbox("District", districts)

    filtered_ac = ac.copy()

    # KPI
    total_constituencies = filtered_ac.shape[0]
    avg_turnout = filtered_ac["turnout_percentage"].mean()

    highest_turnout = filtered_ac.loc[
        filtered_ac["turnout_percentage"].idxmax()
    ]

    lowest_turnout = filtered_ac.loc[
        filtered_ac["turnout_percentage"].idxmin()
    ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Assembly Constituencies", total_constituencies)
    c2.metric("Average Turnout", f"{avg_turnout:.2f}%")
    c3.metric(
        "Highest Turnout",
        f"{highest_turnout['ac_name']}"
    )
    c4.metric(
        "Lowest Turnout",
        f"{lowest_turnout['ac_name']}"
    )

    turnout_map = dict(
        zip(ac["ac_no"], ac["turnout_percentage"])
    )

    # Inject assembly turnout into geojson for tooltip display
    # Normalize to lowercase to handle ALLCAPS in AC dataset vs Title Case in GeoJSON
    ac_name_turnout_map = dict(
        zip(ac["ac_name"].astype(str).str.strip().str.lower(), ac["turnout_percentage"])
    )
    for feature in geojson["features"]:
        assembly_name = str(feature["properties"].get("assembly", "")).strip().lower()
        turnout_val = ac_name_turnout_map.get(assembly_name, None)
        feature["properties"]["ac_voter_turnout"] = (
            round(turnout_val, 2) if turnout_val is not None else "N/A"
        )

    m = folium.Map(
        location=map_location,
        zoom_start=map_zoom,
        tiles="CartoDB dark_matter"
    )

    def style_function(feature):
        ac_no = str(feature["properties"]["ac_no"])
        turnout = turnout_map.get(ac_no, 0)

        if turnout > 70:
            color = "#04ff00"
        elif turnout > 60:
            color = "#6aff00"
        elif turnout > 55:
            color = "#ffea00"
        elif turnout > 50:
            color = "#ffa600"
        elif turnout > 45:
            color = "#ff6f00"
        else:
            color = "#ff4d4d"

        return {
            "fillColor": color,
            "color": "white",
            "weight": 1,
            "fillOpacity": 0.7
        }

    geo = folium.GeoJson(
        geojson,
        style_function=style_function,
        highlight_function=lambda x: {
            "weight": 3,
            "color": "white"
        },
        tooltip=GeoJsonTooltip(
            fields=["assembly", "parliament", "district", "ac_voter_turnout"],
            aliases=["Assembly", "Parliament", "District", "Voter Turnout (%)"],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: #1e1e1e;
                color: white;
                border: 1px solid white;
                border-radius: 6px;
                box-shadow: 3px;
                font-size: 12px;
            """
        )
    )

    geo.add_to(m)

    st.subheader("Assembly Constituency Map")

    st_folium(m, width=1400, height=700)

    st.subheader("Top Assembly Turnout")

    fig = px.bar(
        filtered_ac.sort_values(
            "turnout_percentage",
            ascending=False
        ).head(20),
        x="ac_name",
        y="turnout_percentage",
        title="Top 20 Assembly Constituencies"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(filtered_ac)

    # ── Report Generation ──
    st.subheader("📄 Generate Report")
    st.caption("Download a full PDF fact sheet for all Assembly Constituencies.")
    if st.button("Generate AC Fact Sheet PDF", key="ac_pdf_btn", type="primary"):
        with st.spinner("Building report..."):
            pdf_bytes = generate_ac_report(filtered_ac, pc)
        st.download_button(
            label="⬇️ Download AC Report PDF",
            data=pdf_bytes,
            file_name="AC_Fact_Sheet.pdf",
            mime="application/pdf",
            key="ac_pdf_dl"
        )

# =========================================================
# PARLIAMENTARY VIEW
# =========================================================
elif view_type == "Parliamentary Election":

    st.subheader("Parliamentary Election Analytics")

    # Try detecting turnout column dynamically
    numeric_cols = pc.select_dtypes(include="number").columns.tolist()

    # Find likely turnout column
    turnout_col = "VoterTurnout"
    for col in numeric_cols:
        if "turnout" in col.lower():
            turnout_col = col
            break

    # fallback
    if turnout_col is None:
        turnout_col = numeric_cols[-1]

    # Find parliament name column
    pc_name_col = None

    for col in pc.columns:
        if "pc" in col.lower() and "name" in col.lower():
            pc_name_col = col
            break

    if pc_name_col is None:
        pc_name_col = pc.columns[0]

    parliament_data = (
        pc.groupby(pc_name_col)[turnout_col]
        .mean()
        .reset_index()
    )

    parliament_data.columns = ["Parliament", "VoterTurnout"]

    avg_turnout = parliament_data["VoterTurnout"].mean()

    highest_pc = parliament_data.loc[
        parliament_data["VoterTurnout"].idxmax()
    ]

    lowest_pc = parliament_data.loc[
        parliament_data["VoterTurnout"].idxmin()
    ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Parliamentary Constituencies",
        parliament_data.shape[0]
    )

    c2.metric(
        "Average Parliament Turnout",
        f"{avg_turnout:.2f}%"
    )

    c3.metric(
        "Highest Parliament Turnout",
        highest_pc["Parliament"]
    )

    c4.metric(
        "Lowest Parliament Turnout",
        lowest_pc["Parliament"]
    )

    # PARLIAMENT CHART
    fig = px.bar(
        parliament_data.sort_values(
            "VoterTurnout",
            ascending=False
        ),
        x="Parliament",
        y="VoterTurnout",
        title="Assembly Wise Constituency Turnout"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Resolve column names dynamically (handles CSV renaming like "AC Name" -> "ac_name")
    col_map = {c.lower().replace(" ", "_"): c for c in pc.columns}
    ac_name_col = col_map.get("ac_name") or next(
        (c for c in pc.columns if "ac" in c.lower() and "name" in c.lower()), pc.columns[0]
    )
    turnout_col_pc = col_map.get("voterturnout") or col_map.get("voter_turnout") or next(
        (c for c in pc.columns if "turnout" in c.lower()), pc.columns[-1]
    )

    # Build AC-level turnout map from PC dataset (lowercase for case-insensitive match)
    pc_ac_turnout_map = dict(
        zip(pc[ac_name_col].astype(str).str.strip().str.lower(), pc[turnout_col_pc])
    )

    # GeoJSON name -> PC dataset name corrections (all lowercase)
    name_aliases = {
        "dahisar":                   "dhaisar",
        "versova":                   "varsova",
        "mankhurd shivaji nagar":    "mankhurd shivajinagar",
    }

    # Inject PC-dataset turnout into geojson features by matching assembly name
    for feature in geojson["features"]:
        assembly_name = str(feature["properties"].get("assembly", "")).strip().lower()
        assembly_name = name_aliases.get(assembly_name, assembly_name)
        turnout_val = pc_ac_turnout_map.get(assembly_name, None)
        feature["properties"]["pc_voter_turnout"] = (
            round(turnout_val, 2) if turnout_val is not None else "N/A"
        )

    m = folium.Map(
        location=map_location,
        zoom_start=map_zoom,
        tiles="CartoDB dark_matter"
    )

    def style_pc(feature):
        turnout = feature["properties"].get("pc_voter_turnout", 0)
        if not isinstance(turnout, (int, float)):
            turnout = 0

        if turnout > 60:
            color = "#04ff00"
        elif turnout > 55:
            color = "#d4ff00"
        elif turnout > 50:
            color = "#ffaa00"
        elif turnout > 45:
            color = "#ff7700"
        else:
            color = "#ff4d4d"

        return {
            "fillColor": color,
            "color": "white",
            "weight": 1,
            "fillOpacity": 0.7
        }

    geo = folium.GeoJson(
        geojson,
        style_function=style_pc,
        highlight_function=lambda x: {
            "weight": 3,
            "color": "white"
        },
        tooltip=GeoJsonTooltip(
            fields=[
                "parliament",
                "assembly",
                "district",
                "pc_voter_turnout"
            ],
            aliases=[
                "Parliament",
                "Assembly",
                "District",
                "Assembly Turnout in General Elections (%)"
            ],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: #1e1e1e;
                color: white;
                border: 1px solid white;
                border-radius: 6px;
                box-shadow: 3px;
                font-size: 12px;
            """
        )
    )

    geo.add_to(m)

    st.subheader("Parliamentary Constituency Map")

    st_folium(m, width=1400, height=700)

    st.dataframe(pc)

    # ── Report Generation ──
    st.subheader("📄 Generate Report")
    st.caption("Download a full PDF fact sheet for all Parliamentary Constituencies.")
    if st.button("Generate PC Fact Sheet PDF", key="pc_pdf_btn", type="primary"):
        with st.spinner("Building report..."):
            pdf_bytes = generate_pc_report(pc)
        st.download_button(
            label="⬇️ Download PC Report PDF",
            data=pdf_bytes,
            file_name="PC_Fact_Sheet.pdf",
            mime="application/pdf",
            key="pc_pdf_dl"
        )

# =========================================================
# CONSTITUENCY DEEP DIVE
# =========================================================
elif view_type == "Constituency Deep Dive":
    st.subheader("🔍 Constituency Deep Dive")
    st.caption(
        "Select any Assembly or Parliamentary constituency to compare "
        "Male / Female / Third Gender electors, total votes polled, and voter turnout."
    )

    # ── Determine which dataset to use ──────────────────────────────────────
    dv_type = st.sidebar.radio(
        "Constituency Type",
        ["Assembly Constituency (AC)", "Parliamentary Constituency (PC)"],
        key="dv_type"
    )

    # ── Helper: resolve column names robustly ──────────────────────────────
    def _col(df, *variants):
        """Return first column whose stripped-lowercase name matches any variant."""
        norm = {c: c.lower().replace(" ", "_").replace(".", "") for c in df.columns}
        for c, n in norm.items():
            if any(v == n for v in variants):
                return c
        # Fallback: partial contains match on all keywords in first variant
        for c, n in norm.items():
            if all(kw in n for kw in variants[0].split("_")):
                return c
        return None

    def _safe_int(row, col):
        """Safely extract an integer from a row, returning 0 if col is None or NaN."""
        if col is None:
            return 0
        try:
            v = row[col]
            return int(v) if pd.notna(v) else 0
        except Exception:
            return 0

    def _safe_float(row, col):
        if col is None:
            return 0.0
        try:
            v = row[col]
            return float(v) if pd.notna(v) else 0.0
        except Exception:
            return 0.0

    # ── AC Deep Dive ──────────────────────────────────────────────────────
    if dv_type == "Assembly Constituency (AC)":

        # Handles both raw Excel column names (Male, Female, Other, Total, Male.1 …)
        # and cleaned CSV names (electors_male, electors_female, electors_other,
        # electors_total, voters_total, turnout_percentage, ac_name …)
        ac_name_col  = _col(ac, "ac_name") or _col(ac, "ac_name") or ac.columns[1]
        male_e_col   = _col(ac, "electors_male",  "male")
        female_e_col = _col(ac, "electors_female","female")
        other_e_col  = _col(ac, "electors_other", "other")
        total_e_col  = _col(ac, "electors_total", "total")

        # Voters by gender: Male.1 / voters_male, Female.1 / voters_female, Other.1 / voters_other
        male_v_col   = _col(ac, "voters_male",   "male1",   "male_1")
        female_v_col = _col(ac, "voters_female", "female1", "female_1")
        other_v_col  = _col(ac, "voters_other",  "other1",  "other_1")

        # Voters total: prefer voters_total, fall back to total1 / total_1
        voters_t_col = "Total.1"
        if voters_t_col is None:
            total_candidates = [c for c in ac.columns if "total" in c.lower().replace(".", "")]
            voters_t_col = total_candidates[1] if len(total_candidates) > 1 else (total_candidates[0] if total_candidates else None)

        turnout_col  = _col(ac, "turnout_percentage", "total_percentage", "voter_turnout")
        if turnout_col is None:
            turnout_col = next((c for c in ac.columns if "turnout" in c.lower() or "percentage" in c.lower()), None)

        ac_names = sorted(ac[ac_name_col].dropna().astype(str).unique())
        selected_ac = st.sidebar.selectbox("Select Assembly Constituency", ac_names, key="sel_ac")

        row = ac[ac[ac_name_col].astype(str) == selected_ac].iloc[0]

        # Electors
        male_e   = _safe_int(row, male_e_col)
        female_e = _safe_int(row, female_e_col)
        other_e  = _safe_int(row, other_e_col)
        total_e  = _safe_int(row, total_e_col) or (male_e + female_e + other_e)

        # Votes polled by gender
        male_v   = _safe_int(row, male_v_col)
        female_v = _safe_int(row, female_v_col)
        other_v  = _safe_int(row, other_v_col)
        total_v  = _safe_int(row, voters_t_col) or (male_v + female_v + other_v)

        raw_turnout = _safe_float(row, turnout_col)
        turnout_pct = raw_turnout * 100 if raw_turnout <= 1 else raw_turnout

        # Per-gender turnout %
        male_t_pct   = (male_v   / male_e   * 100) if male_e   else 0
        female_t_pct = (female_v / female_e * 100) if female_e else 0
        other_t_pct  = (other_v  / other_e  * 100) if other_e  else 0

        COLOR_MAP = {"Male": "#12acff", "Female": "#ec52c8", "Third Gender": "#8957e5"}

        # ── KPI row 1: Electors ────────────────────────────────────────────
        st.markdown(f"### 🏛️ {selected_ac} — Assembly Constituency")
        st.caption("Electors")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("👨 Male Electors",         f"{male_e:,}")
        k2.metric("👩 Female Electors",       f"{female_e:,}")
        k3.metric("⚧ Third Gender Electors",  f"{other_e:,}")
        k4.metric("👥 Total Electors",         f"{total_e:,}")

        # ── KPI row 2: Votes Polled ────────────────────────────────────────
        st.caption("Votes Polled")
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("👨 Male Votes",          f"{male_v:,}")
        v2.metric("👩 Female Votes",        f"{female_v:,}")
        v3.metric("⚧ Third Gender Votes",   f"{other_v:,}")
        v4.metric("🗳️ Total Votes Polled",  f"{total_v:,}")
        v5.metric("📊 Overall Turnout",      f"{turnout_pct:.2f}%")

        st.divider()

        # ── Row 1: Electors vs Votes Polled grouped bar ────────────────────
        st.subheader("Electors vs Votes Polled by Gender")
        compare_df = pd.DataFrame({
            "Gender":   ["Male", "Female", "Third Gender"],
            "Electors": [male_e, female_e, other_e],
            "Votes Polled": [male_v, female_v, other_v],
        }).melt(id_vars="Gender", var_name="Type", value_name="Count")

        fig_compare = px.bar(
            compare_df,
            x="Gender", y="Count", color="Type", barmode="group",
            color_discrete_map={"Electors": "#30363d", "Votes Polled": "#238636"},
            text_auto=True,
            title="Registered Electors vs Actual Votes Polled — by Gender",
        )
        fig_compare.update_traces(textposition="outside")
        fig_compare.update_layout(plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
        st.plotly_chart(fig_compare, use_container_width=True)

        st.divider()

        # ── Row 2: Gender share pies side by side ─────────────────────────
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Electorate Gender Share")
            elector_df = pd.DataFrame({
                "Category": ["Male", "Female", "Third Gender"],
                "Electors": [male_e, female_e, other_e],
            })
            fig_epie = px.pie(
                elector_df, names="Category", values="Electors",
                color="Category", color_discrete_map=COLOR_MAP,
                title="Share of Total Electors", hole=0.45,
            )
            fig_epie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_epie, use_container_width=True)

        with col_right:
            st.subheader("Votes Polled Gender Share")
            votes_df = pd.DataFrame({
                "Category": ["Male", "Female", "Third Gender"],
                "Votes":    [male_v, female_v, other_v],
            })
            fig_vpie = px.pie(
                votes_df, names="Category", values="Votes",
                color="Category", color_discrete_map=COLOR_MAP,
                title="Share of Total Votes Polled", hole=0.45,
            )
            fig_vpie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_vpie, use_container_width=True)

        st.divider()

        # ── Row 3: Per-gender turnout % + overall participation ───────────
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Voter Turnout by Gender")
            turnout_df = pd.DataFrame({
                "Gender":    ["Male", "Female", "Third Gender"],
                "Turnout %": [male_t_pct, female_t_pct, other_t_pct],
            })
            fig_gt = px.bar(
                turnout_df, x="Gender", y="Turnout %",
                color="Gender", color_discrete_map=COLOR_MAP,
                range_y=[0, 100], text_auto=".1f",
                title="Turnout % per Gender",
            )
            fig_gt.update_traces(texttemplate="%{y:.1f}%", textposition="outside")
            fig_gt.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_gt, use_container_width=True)

        with col_b:
            st.subheader("Overall Participation")
            participation_df = pd.DataFrame({
                "Metric": ["Votes Polled", "Did Not Vote"],
                "Count":  [total_v, max(total_e - total_v, 0)],
            })
            fig_part = px.bar(
                participation_df, x="Metric", y="Count",
                color="Metric",
                color_discrete_map={"Votes Polled": "#34EB59", "Did Not Vote": "#f33835"},
                text_auto=True, title="Total Votes Polled vs Abstentions",
            )
            fig_part.update_traces(textposition="outside")
            fig_part.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_part, use_container_width=True)

            # vs state average
            if turnout_col:
                state_avg = ac[turnout_col].apply(
                    lambda v: v * 100 if pd.notna(v) and v <= 1 else (v if pd.notna(v) else 0)
                ).mean()
            else:
                state_avg = 0
            st.metric(
                "vs. State Average",
                f"{state_avg:.2f}%",
                delta=f"{turnout_pct - state_avg:+.2f}%",
                delta_color="normal",
            )

        st.divider()

        # ── Raw data table ─────────────────────────────────────────────────
        with st.expander("📋 Raw Data for this Constituency"):
            st.dataframe(ac[ac[ac_name_col].astype(str) == selected_ac])

    # ── PC Deep Dive ───────────────────────────────────────────────────────
    else:
        # PC columns: District No., District Name, PC No., PC Name, AC No., AC Name,
        #             Male, Female, Third Gender, Total (electors),
        #             Votes Polled, NOTA, Postal Ballots, Total.1 (votes total), VoterTurnout

        pc_name_col   = _col(pc, "pc_name")  or "PC Name"
        ac_name_col   = _col(pc, "ac_name")  or "AC Name"
        male_col      = _col(pc, "male")
        female_col    = _col(pc, "female")
        tg_col        = next((c for c in pc.columns if "third" in c.lower() or "gender" in c.lower()), None)
        total_e_col   = _col(pc, "total")
        polled_col    = next((c for c in pc.columns if "polled" in c.lower()),        None)
        turnout_col   = next((c for c in pc.columns if "turnout" in c.lower()),       None)

        pc_names = sorted(pc[pc_name_col].dropna().astype(str).unique())
        selected_pc = st.sidebar.selectbox("Select Parliamentary Constituency", pc_names, key="sel_pc")

        group = pc[pc[pc_name_col].astype(str) == selected_pc].copy()

        # Aggregate across AC rows safely
        def _sum_col(df, col):
            if col is None: return 0
            return int(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())

        male_e       = _sum_col(group, male_col)
        female_e     = _sum_col(group, female_col)
        other_e      = _sum_col(group, tg_col)
        total_e      = _sum_col(group, total_e_col) or (male_e + female_e + other_e)
        votes_polled = _sum_col(group, polled_col)
        avg_turnout  = float(pd.to_numeric(group[turnout_col], errors="coerce").mean()) if turnout_col else 0

        # ── KPI Cards ─────────────────────────────────────────────────────
        st.markdown(f"### 🏛️ {selected_pc} — Parliamentary Constituency")
        st.caption(f"{len(group)} Assembly Segments")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("👨 Male Electors",         f"{male_e:,}")
        k2.metric("👩 Female Electors",       f"{female_e:,}")
        k3.metric("⚧ Third Gender Electors",  f"{other_e:,}")
        k4.metric("🗳️ Total Votes Polled",    f"{votes_polled:,}")
        k5.metric("📊 Avg Turnout",            f"{avg_turnout:.2f}%")

        st.divider()

        # ── Electorate breakdown ───────────────────────────────────────────
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Electorate Composition (PC Total)")
            elector_df = pd.DataFrame({
                "Category": ["Male", "Female", "Third Gender"],
                "Electors": [male_e, female_e, other_e]
            })
            fig_electors = px.bar(
                elector_df,
                x="Category",
                y="Electors",
                color="Category",
                color_discrete_map={
                    "Male":         "#319bec",
                    "Female":       "#ea42b5",
                    "Third Gender": "#8957e5"
                },
                title=f"Electors by Gender — {selected_pc}",
                text_auto=True,
            )
            fig_electors.update_traces(textposition="outside")
            fig_electors.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_electors, use_container_width=True)

        with col_right:
            st.subheader("Electorate Share (%)")
            fig_pie = px.pie(
                elector_df,
                names="Category",
                values="Electors",
                color="Category",
                color_discrete_map={
                    "Male":         "#319bec",
                    "Female":       "#ea42b5",
                    "Third Gender": "#8957e5"
                },
                title=f"Gender Share of Electorate — {selected_pc}",
                hole=0.45,
            )
            fig_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # ── Votes polled + turnout ─────────────────────────────────────────
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Votes Polled vs Total Electors")
            participation_df = pd.DataFrame({
                "Metric": ["Votes Polled", "Did Not Vote"],
                "Count":  [votes_polled, max(total_e - votes_polled, 0)]
            })
            fig_part = px.bar(
                participation_df,
                x="Metric",
                y="Count",
                color="Metric",
                color_discrete_map={
                    "Votes Polled": "#23F14C",
                    "Did Not Vote": "#f04845"
                },
                title="Total Participation (PC Aggregate)",
                text_auto=True,
            )
            fig_part.update_traces(textposition="outside")
            fig_part.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_part, use_container_width=True)

        with col_b:
            st.subheader("Assembly Segment Turnout within PC")
            if turnout_col and ac_name_col:
                seg_df = group[[ac_name_col, turnout_col]].copy()
                seg_df.columns = ["Assembly Segment", "Turnout (%)"]
                fig_seg = px.bar(
                    seg_df.sort_values("Turnout (%)", ascending=True),
                    x="Turnout (%)",
                    y="Assembly Segment",
                    orientation="h",
                    color="Turnout (%)",
                    color_continuous_scale=["#f2514e", "#ffa600", "#4BED6B"],
                    title=f"Segment-wise Turnout — {selected_pc}",
                    range_x=[0, 100],
                    text_auto=".1f",
                )
                fig_seg.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
                fig_seg.update_layout(
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_seg, use_container_width=True)

        st.divider()

        # ── Segment-level electorate breakdown ────────────────────────────
        st.subheader("📊 Segment-wise Electorate Breakdown")
        if male_col and female_col and tg_col and ac_name_col:
            seg_detail = group[[ac_name_col, male_col, female_col, tg_col]].copy()
            seg_detail.columns = ["Assembly Segment", "Male", "Female", "Third Gender"]
            seg_melted = seg_detail.melt(
                id_vars="Assembly Segment",
                var_name="Gender",
                value_name="Electors"
            )
            fig_grouped = px.bar(
                seg_melted,
                x="Assembly Segment",
                y="Electors",
                color="Gender",
                barmode="group",
                color_discrete_map={
                    "Male":         "#319bec",
                    "Female":       "#ea42b5",
                    "Third Gender": "#8957e5"
                },
                title=f"Electors per Assembly Segment — {selected_pc}",
                text_auto=True,
            )
            fig_grouped.update_traces(textposition="outside")
            fig_grouped.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig_grouped, use_container_width=True)

        st.divider()

        # ── Raw data table ─────────────────────────────────────────────────
        with st.expander("📋 Raw Data for this PC"):
            st.dataframe(group)
# =========================================================
# AC vs PC COMPARISON
# =========================================================
else:
    st.subheader("⚖️ AC vs PC Comparison")
    st.caption(
        "Compare how a specific Assembly Constituency voted in the Assembly Election "
        "vs how the same segment performed in the Parliamentary Election — "
        "electors, voters, turnout, and gender breakdown side by side."
    )

    # ── Helper functions (mirror from Deep Dive section) ──────────────────
    def _col2(df, *variants):
        norm = {c: c.lower().replace(" ", "_").replace(".", "") for c in df.columns}
        for c, n in norm.items():
            if any(v == n for v in variants):
                return c
        for c, n in norm.items():
            if all(kw in n for kw in variants[0].split("_")):
                return c
        return None

    def _safe_int2(row, col):
        if col is None:
            return 0
        try:
            v = row[col]
            return int(v) if pd.notna(v) else 0
        except Exception:
            return 0

    def _safe_float2(row, col):
        if col is None:
            return 0.0
        try:
            v = row[col]
            return float(v) if pd.notna(v) else 0.0
        except Exception:
            return 0.0

    # ── AC column resolution ──────────────────────────────────────────────
    ac_name_col   = _col2(ac, "ac_name") or ac.columns[1]
    ac_male_e     = _col2(ac, "electors_male",  "male")
    ac_female_e   = _col2(ac, "electors_female", "female")
    ac_other_e    = _col2(ac, "electors_other",  "other")
    ac_total_e    = _col2(ac, "electors_total",  "total")
    ac_male_v     = _col2(ac, "voters_male",  "male1",  "male_1")
    ac_female_v   = _col2(ac, "voters_female","female1","female_1")
    ac_other_v    = _col2(ac, "voters_other", "other1", "other_1")
    ac_voters_t = "Total.1"
    if ac_voters_t is None:
        _tc = [c for c in ac.columns if "total" in c.lower().replace(".", "")]
        ac_voters_t = _tc[1] if len(_tc) > 1 else (_tc[0] if _tc else None)
    ac_turnout_col = _col2(ac, "turnout_percentage", "total_percentage", "voter_turnout")
    if ac_turnout_col is None:
        ac_turnout_col = next((c for c in ac.columns if "turnout" in c.lower() or "percentage" in c.lower()), None)

    # ── PC column resolution ──────────────────────────────────────────────
    pc_ac_name_col  = _col2(pc, "ac_name")  or "AC Name"
    pc_pc_name_col  = _col2(pc, "pc_name")  or "PC Name"
    # AC-level electors stored inside PC dataset (assembly election figures)
    pc_male_col     = _col2(pc, "electors_male",  "male")
    pc_female_col   = _col2(pc, "electors_female","female")
    pc_tg_col       = next((c for c in pc.columns if "third" in c.lower() or "gender" in c.lower()), None)
    # PC-level total electors (parliamentary election) — distinct from electors_total (AC figure)
    pc_total_e_col  = next((c for c in pc.columns if "total_electors_pc" in c.lower().replace(" ", "_")), None) \
                      or _col2(pc, "total_electors_pc")
    # Votes polled in parliamentary election
    pc_polled_col   = next((c for c in pc.columns if "votes_polled" in c.lower().replace(" ", "_")
                            or "polled" in c.lower()), None)
    pc_turnout_col  = next((c for c in pc.columns if "turnout" in c.lower()), None)

    # ── Sidebar: pick constituency ─────────────────────────────────────────
    ac_names_list = sorted(ac[ac_name_col].dropna().astype(str).unique())
    selected_ac = st.sidebar.selectbox("Select Assembly Constituency", ac_names_list, key="cmp_sel_ac")

    # ── Pull AC row ────────────────────────────────────────────────────────
    ac_rows = ac[ac[ac_name_col].astype(str) == selected_ac]
    if ac_rows.empty:
        st.warning(f"No AC data found for '{selected_ac}'.")
        st.stop()
    ac_row = ac_rows.iloc[0]

    ac_m_e  = _safe_int2(ac_row, ac_male_e)
    ac_f_e  = _safe_int2(ac_row, ac_female_e)
    ac_o_e  = _safe_int2(ac_row, ac_other_e)
    ac_t_e  = _safe_int2(ac_row, ac_total_e) or (ac_m_e + ac_f_e + ac_o_e)
    ac_m_v  = _safe_int2(ac_row, ac_male_v)
    ac_f_v  = _safe_int2(ac_row, ac_female_v)
    ac_o_v  = _safe_int2(ac_row, ac_other_v)
    ac_t_v  = _safe_int2(ac_row, ac_voters_t) or (ac_m_v + ac_f_v + ac_o_v)
    raw_to  = _safe_float2(ac_row, ac_turnout_col)
    ac_turnout = raw_to * 100 if raw_to <= 1 else raw_to

    # ── Pull PC row (match on AC name, case-insensitive) ──────────────────
    pc_rows = pc[pc[pc_ac_name_col].astype(str).str.strip().str.lower() == selected_ac.strip().lower()]

    pc_data_available = not pc_rows.empty
    if pc_data_available:
        pc_row = pc_rows.iloc[0]
        pc_m_e   = _safe_int2(pc_row, pc_male_col)
        pc_f_e   = _safe_int2(pc_row, pc_female_col)
        pc_o_e   = _safe_int2(pc_row, pc_tg_col)
        # Use total_electors_pc for parliamentary electors (not electors_total which is AC figure)
        pc_t_e   = _safe_int2(pc_row, pc_total_e_col) or (pc_m_e + pc_f_e + pc_o_e)
        # Use votes_polled for parliamentary votes (not voters_total which is AC figure)
        pc_t_v   = _safe_int2(pc_row, pc_polled_col)
        pc_to    = _safe_float2(pc_row, pc_turnout_col)
        pc_name  = str(pc_row[pc_pc_name_col]) if pc_pc_name_col else "N/A"
    else:
        pc_m_e = pc_f_e = pc_o_e = pc_t_e = pc_t_v = 0
        pc_to = 0.0
        pc_name = "N/A"
        st.info(
            f"⚠️ No matching PC data found for '{selected_ac}'. "
            "AC data is shown; PC columns will show 0. "
            "Check that AC names match between the two datasets."
        )

    COLOR_AC = "#11eff3"   # blue  → Assembly
    COLOR_PC = "#fdbf3a"   # amber → Parliamentary

    st.markdown(f"### 📍 {selected_ac}")
    if pc_data_available:
        st.caption(f"Assembly Constituency &nbsp;|&nbsp; Part of **{pc_name}** Parliamentary Constituency")

    st.divider()

    # ── KPI: Electors side-by-side ────────────────────────────────────────
    st.subheader("🗂️ Registered Electors")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👨 Male",         f"{ac_m_e:,}",  delta=f"PC: {pc_m_e:,}",  delta_color="off")
    k2.metric("👩 Female",       f"{ac_f_e:,}",  delta=f"PC: {pc_f_e:,}",  delta_color="off")
    k3.metric("⚧ Third Gender",  f"{ac_o_e:,}",  delta=f"PC: {pc_o_e:,}",  delta_color="off")
    k4.metric("👥 Total",         f"{ac_t_e:,}",  delta=f"PC: {pc_t_e:,}",  delta_color="off")
    st.caption("Primary value = Assembly Election figure &nbsp;|&nbsp; Delta = Parliamentary Election figure")

    st.divider()

    # ── KPI: Votes & Turnout ──────────────────────────────────────────────
    st.subheader("🗳️ Votes Polled & Turnout")
    v1, v2, v3 = st.columns(3)
    v1.metric("🗳️ Votes Polled (AC)", f"{ac_t_v:,}")
    v2.metric("🗳️ Votes Polled (PC)", f"{pc_t_v:,}")
    turnout_delta = ac_turnout - pc_to
    v3.metric("📊 Turnout (AC vs PC)",
              f"AC {ac_turnout:.2f}%",
              delta=f"{turnout_delta:+.2f}% vs PC {pc_to:.2f}%",
              delta_color="normal")

    st.divider()

    # ── Chart 1: Electors comparison grouped bar ──────────────────────────
    st.subheader("Electors — AC vs PC (by Gender)")
    electors_cmp = pd.DataFrame({
        "Gender":     ["Male", "Female", "Third Gender"],
        "Assembly":   [ac_m_e,  ac_f_e,  ac_o_e],
        "Parliament": [pc_m_e,  pc_f_e,  pc_o_e],
    }).melt(id_vars="Gender", var_name="Election", value_name="Electors")

    fig_elec = px.bar(
        electors_cmp, x="Gender", y="Electors", color="Election", barmode="group",
        color_discrete_map={"Assembly": COLOR_AC, "Parliament": COLOR_PC},
        text_auto=True, title="Registered Electors: Assembly vs Parliamentary Election",
    )
    fig_elec.update_traces(textposition="outside")
    fig_elec.update_layout(plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
    st.plotly_chart(fig_elec, use_container_width=True)

    st.divider()

    # ── Chart 2: Total electors vs votes polled (both elections) ──────────
    st.subheader("Electors vs Votes Polled — Both Elections")
    participation_cmp = pd.DataFrame({
        "Category":  ["AC Electors", "AC Votes Polled", "PC Electors", "PC Votes Polled"],
        "Count":     [ac_t_e,        ac_t_v,             pc_t_e,        pc_t_v],
        "Election":  ["Assembly",    "Assembly",          "Parliament",  "Parliament"],
    })
    fig_part = px.bar(
        participation_cmp, x="Category", y="Count", color="Election", barmode="group",
        color_discrete_map={"Assembly": COLOR_AC, "Parliament": COLOR_PC},
        text_auto=True,
        title="Total Electors vs Actual Votes Polled — Assembly & Parliamentary",
    )
    fig_part.update_traces(textposition="outside")
    fig_part.update_layout(plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
    st.plotly_chart(fig_part, use_container_width=True)

    st.divider()

    # ── Chart 3: Turnout gauge-style bar ──────────────────────────────────
    st.subheader("Voter Turnout Comparison")
    col_l, col_r = st.columns(2)

    with col_l:
        turnout_df = pd.DataFrame({
            "Election": ["Assembly (AC)", "Parliamentary (PC)"],
            "Turnout %": [ac_turnout, pc_to],
        })
        fig_to = px.bar(
            turnout_df, x="Election", y="Turnout %",
            color="Election",
            color_discrete_map={"Assembly (AC)": COLOR_AC, "Parliamentary (PC)": COLOR_PC},
            range_y=[0, 100], text_auto=".2f",
            title="Turnout %: Assembly vs Parliamentary",
        )
        fig_to.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
        fig_to.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_to, use_container_width=True)

    with col_r:
        # Abstentions comparison
        abs_df = pd.DataFrame({
            "Election":    ["Assembly", "Assembly", "Parliamentary", "Parliamentary"],
            "Metric":      ["Voted", "Abstained", "Voted", "Abstained"],
            "Count":       [ac_t_v, max(ac_t_e - ac_t_v, 0), pc_t_v, max(pc_t_e - pc_t_v, 0)],
        })
        fig_abs = px.bar(
            abs_df, x="Election", y="Count", color="Metric", barmode="stack",
            color_discrete_map={"Voted": "#2CE852", "Abstained": "#f34c4a"},
            text_auto=True,
            title="Voted vs Abstained — Assembly vs Parliamentary",
        )
        fig_abs.update_traces(textposition="inside")
        fig_abs.update_layout(plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
        st.plotly_chart(fig_abs, use_container_width=True)

    st.divider()

    # ── Summary table ──────────────────────────────────────────────────────
    st.subheader("📋 Summary Table")
    summary = pd.DataFrame({
        "Metric": [
            "Male Electors", "Female Electors", "Third Gender Electors", "Total Electors",
            "Votes Polled", "Voter Turnout (%)"
        ],
        "Assembly Election (AC)": [
            f"{ac_m_e:,}", f"{ac_f_e:,}", f"{ac_o_e:,}", f"{ac_t_e:,}",
            f"{ac_t_v:,}", f"{ac_turnout:.2f}%"
        ],
        "Parliamentary Election (PC)": [
            f"{pc_m_e:,}", f"{pc_f_e:,}", f"{pc_o_e:,}", f"{pc_t_e:,}",
            f"{pc_t_v:,}", f"{pc_to:.2f}%"
        ],
        "Difference": [
            f"{ac_m_e - pc_m_e:+,}", f"{ac_f_e - pc_f_e:+,}",
            f"{ac_o_e - pc_o_e:+,}", f"{ac_t_e - pc_t_e:+,}",
            f"{ac_t_v - pc_t_v:+,}", f"{ac_turnout - pc_to:+.2f}%"
        ],
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # ── Raw data expanders ────────────────────────────────────────────────
    with st.expander("📂 Raw AC Data"):
        st.dataframe(ac_rows, use_container_width=True)

    if pc_data_available:
        with st.expander("📂 Raw PC Data"):
            st.dataframe(pc_rows, use_container_width=True)