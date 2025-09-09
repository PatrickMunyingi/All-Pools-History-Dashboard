# dashboard.py
import os
import urllib.parse
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text


# =========================
#  Load local secrets into env (for dev)
# =========================
if "azure_sql" in st.secrets:
    cfg = st.secrets["azure_sql"]
    os.environ["AZURE_SQL_SERVER"]   = cfg.get("server", "")
    os.environ["AZURE_SQL_DATABASE"] = cfg.get("database", "")
    os.environ["AZURE_SQL_USER"]     = cfg.get("user", "")
    os.environ["AZURE_SQL_PASSWORD"] = cfg.get("password", "")


# =========================
#  Minimal login gate (uses same SQL creds)
# =========================
USERNAME = os.getenv("AZURE_SQL_USER", "app_rw")
PASSWORD = os.getenv("AZURE_SQL_PASSWORD", "ARC@Data1")  # fallback for local

def login_gate():
    if st.session_state.get("authed_user"):
        return True

    st.sidebar.header("🔑 Login Required")
    u = st.sidebar.text_input("Username")
    p = st.sidebar.text_input("Password", type="password")
    go = st.sidebar.button("Login")

    if go:
        if u == USERNAME and p == PASSWORD:
            st.session_state["authed_user"] = u
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        else:
            st.sidebar.error("Invalid credentials")
    st.stop()

login_gate()


# =========================
#  DB ENGINE (ODBC via pyodbc)
# =========================
def get_engine():
    """
    Azure SQL over ODBC (pyodbc).
    Requires env vars:
      AZURE_SQL_SERVER, AZURE_SQL_DATABASE, AZURE_SQL_USER, AZURE_SQL_PASSWORD
    """
    server   = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DATABASE")
    user     = os.getenv("AZURE_SQL_USER")
    pwd      = os.getenv("AZURE_SQL_PASSWORD")
    driver   = "ODBC Driver 18 for SQL Server"

    missing = [k for k, v in {
        "AZURE_SQL_SERVER": server,
        "AZURE_SQL_DATABASE": database,
        "AZURE_SQL_USER": user,
        "AZURE_SQL_PASSWORD": pwd,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    odbc_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};PWD={pwd};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    params = urllib.parse.quote_plus(odbc_str)

    eng = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        fast_executemany=True,
        pool_pre_ping=True,
        future=True,
    )

    # ping
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    return eng


@st.cache_resource(show_spinner=False)
def cached_engine():
    return get_engine()


def sql_read(query: str) -> pd.DataFrame:
    with cached_engine().begin() as conn:
        return pd.read_sql(text(query), conn)


def sort_pools(pool_list):
    safe = [str(x) for x in pool_list]
    return sorted(safe, key=lambda x: (int("".join(filter(str.isdigit, x)) or 0), x))


# =========================
#  STREAMLIT CHROME
# =========================
st.set_page_config(page_title="All Pools History Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
        [data-testid="stHeader"] { height: 0rem; }
        [data-testid="stToolbar"] { display: none; }
        @keyframes fadeInBounce {
            0% {opacity: 0; transform: translateY(-20px);}
            50% {opacity: 0.5; transform: translateY(5px);}
            100% {opacity: 1; transform: translateY(0);}
        }
        .animated-title {
            text-align: center;
            color: #1E90FF;
            font-size: 40px;
            font-weight: bold;
            animation: fadeInBounce 1.5s ease-out;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown("<h1 class='animated-title'>ALL POOLS HISTORY DASHBOARD</h1>", unsafe_allow_html=True)

today = datetime.today()
first_of_month = today.replace(day=1).strftime("%B %d, %Y")
st.markdown(f"** Data as of {first_of_month}**")


# =========================
#  Connectivity Check
# =========================
with st.expander("🔌 Connectivity Check (Azure SQL)", expanded=False):
    try:
        with cached_engine().connect() as c:
            who = c.execute(text("SELECT DB_NAME() AS db, SUSER_SNAME() AS suser")).mappings().first()
            st.success(f"Connected ✅  DB={who['db']}  As={who['suser']}")
            try:
                sample = pd.read_sql(text("SELECT TOP 5 * FROM dbo.sov"), c)
                st.write("Sample from dbo.sov:", sample)
            except Exception as e:
                st.info(f"Could not read dbo.sov: {e}")
    except Exception as e:
        st.error(f"Connection failed: {e}")


# =========================
#  BUSINESS SWITCHER
# =========================
Business_Types = st.selectbox("Choose Business Type", ("", "SOVEREIGN BUSINESS", "IIS"))


# =========================
#  SOVEREIGN BUSINESS
# =========================
if Business_Types == "SOVEREIGN BUSINESS":

    @st.cache_data(show_spinner=False)
    def load_sov_from_sql() -> pd.DataFrame:
        q = "SELECT * FROM dbo.sov;"
        df = sql_read(q)

        # Numeric coercion
        for c in ["Premium", "Attachment", "Exhaustion", "Coverage", "Claims"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # Master Pool
        if "Pool" in df.columns:
            df["Pool"] = df["Pool"].astype(str)
            df["Master Pool"] = df["Pool"].str.extract(r"(\d+)")
            df["Master Pool"] = df["Master Pool"].fillna(df["Pool"])
        return df

    df = load_sov_from_sql()
    premium_payers = [c for c in df.columns if str(c).startswith("Premium Financed by")]

    # ---------- Filters ----------
    with st.sidebar.expander("Filters", expanded=True):
        show_sub_pools = st.checkbox("Show Sub-Pools (like 10A, 10B)", value=False)
        pool_column = "Pool" if show_sub_pools else "Master Pool"

        def safe_unique(col):
            return df[col].dropna().astype(str).unique().tolist() if col in df.columns else []

        sorted_pool_options = sort_pools(safe_unique(pool_column))
        select_all_pools = st.checkbox("Select All Pools", value=True)
        pool = st.multiselect("Select Pool:", options=sorted_pool_options,
                              default=sorted_pool_options if select_all_pools else [])

        policy_types = safe_unique("Policy Type")
        select_all_policy_types = st.checkbox("Select All Policy Types", value=True)
        policy_type = st.multiselect("Policy Type:", options=policy_types,
                                     default=policy_types if select_all_policy_types else [])

        countries = safe_unique("Country")
        select_all_countries = st.checkbox("Select All Countries", value=True)
        country = st.multiselect("Country:", options=countries,
                                 default=countries if select_all_countries else [])

        regions = safe_unique("Region")
        select_all_regions = st.checkbox("Select All Regions", value=True)
        region = st.multiselect("Region:", options=regions,
                                default=regions if select_all_regions else [])

        perils = safe_unique("Peril")
        select_all_peril = st.checkbox("Select All Perils", value=True)
        peril = st.multiselect("Peril:", options=perils, default=perils if select_all_peril else [])

        crops = safe_unique("Crop Type")
        select_all_crop_types = st.checkbox("Select All Crop Types", value=True)
        crop_type = st.multiselect("Crop Type:", options=crops,
                                   default=crops if select_all_crop_types else [])

    def _isin(df_, col, vals):
        return df_[col].astype(str).isin([str(v) for v in vals]) if col in df_.columns else True

    df_selection = df[
        _isin(df, pool_column, pool)
        & _isin(df, "Policy Type", policy_type)
        & _isin(df, "Country", country)
        & _isin(df, "Peril", peril)
        & _isin(df, "Region", region)
        & _isin(df, "Crop Type", crop_type)
    ].copy()

    num_policies = len(df_selection)

    option = st.selectbox(
        "What would you like to view?",
        ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history"),
    )

    # ---------- Section 1 ----------
    if option == "Premium and country basic Information":
        total_premium  = df_selection.get("Premium",  pd.Series(dtype=float)).sum()
        total_claims   = df_selection.get("Claims",   pd.Series(dtype=float)).sum()
        total_coverage = df_selection.get("Coverage", pd.Series(dtype=float)).sum()
        loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Premium", f"US ${total_premium:,.0f}")
        c2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
        c3.metric("Coverage", f"US ${total_coverage:,.0f}")
        c4.metric("Claims", f"US ${total_claims:,.0f}")
        c5.metric("Number of Policies", f"{num_policies}")

        col1, col2, col3 = st.columns(3)

        with col1:
            if not df_selection.empty and {"Premium", "Coverage"}.intersection(df_selection.columns):
                trend_metric = st.radio("Select Metric", ["Premium", "Coverage"], horizontal=True)
                if trend_metric in df_selection.columns:
                    pool_trend = (
                        df_selection.groupby(pool_column, dropna=False)[trend_metric]
                        .sum().reset_index()
                    )
                    pool_trend[pool_column] = pool_trend[pool_column].astype(str)
                    pool_trend["__num"] = pool_trend[pool_column].str.extract(r"(\d+)").fillna("0").astype(int)
                    pool_trend["__has_suffix"] = pool_trend[pool_column].str.contains(r"[A-Za-z]")
                    ordered = pool_trend.sort_values(["__has_suffix", "__num"])[pool_column].tolist()
                    pool_trend[pool_column] = pd.Categorical(pool_trend[pool_column], categories=ordered, ordered=True)

                    fig = px.line(
                        pool_trend.sort_values(pool_column),
                        x=pool_column, y=trend_metric, markers=True,
                        title=f"Yearly {trend_metric}s Over Time", template="plotly_white",
                        category_orders={pool_column: ordered},
                    )
                    st.plotly_chart(fig, use_container_width=True)

        with col2:
            if "Country" in df_selection.columns and not df_selection.empty:
                country_count = df_selection["Country"].value_counts().reset_index()
                country_count.columns = ["Country", "Count"]
                fig2 = px.bar(country_count, x="Count", y="Country", orientation="h", title="Country Count")
                st.plotly_chart(fig2, use_container_width=True)

        with col3:
            if "Policy Type" in df_selection.columns and not df_selection.empty:
                pt = df_selection["Policy Type"].value_counts().reset_index()
                pt.columns = ["Policy Type", "Count"]
                fig3 = px.pie(pt, names="Policy Type", values="Count", hole=0.6, title="Policy Type Distribution")
                st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### Filtered Data")
        export_df = df_selection.copy()
        if "Rate-On-Line" in export_df.columns:
            export_df["Rate-On-Line"] = pd.to_numeric(export_df["Rate-On-Line"], errors="coerce")
            export_df["Rate-On-Line"] = export_df["Rate-On-Line"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        if "Ceding %" in export_df.columns:
            export_df["Ceding %"] = pd.to_numeric(export_df["Ceding %"], errors="coerce")
            export_df["Ceding %"] = export_df["Ceding %"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        for col in export_df.columns:
            if col not in ["Rate-On-Line", "Ceding %", "Premium Loading"]:
                if pd.api.types.is_numeric_dtype(export_df[col]):
                    export_df[col] = export_df[col].apply(lambda x: f"{x:,.0f}")
        st.dataframe(export_df)

    # ---------- Section 2 ----------
    elif option == "Premium financing and Tracker":
        mapping = {col: col.replace("Premium Financed by ", "") for col in premium_payers}
        st.markdown("### Select Premium Payers",
                    help="Note: For Pools 1–5 there was no Premium Financing. It begins from Pool 6 (2019/2020).")
        
        select_all = st.checkbox("Select All Premium Payers", value=True)
        picked_display = st.multiselect("Premium Payers", mapping.values(), default=mapping.values() if select_all else [])
        picked_cols = [k for k, v in mapping.items() if v in picked_display]

        if not picked_cols:
            df_pf = df_selection
            total_prem = df_pf.get("Premium", pd.Series(dtype=float)).sum()
        else:
            mask = df_selection[picked_cols].fillna(0).sum(axis=1) > 0
            df_pf = df_selection[mask]
            total_prem = df_pf[picked_cols].sum().sum()

        total_claims = df_selection.get("Claims", pd.Series(dtype=float)).sum()
        total_cov = df_selection.get("Coverage", pd.Series(dtype=float)).sum()
        loss_ratio = (total_claims / total_prem) * 100 if total_prem > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Premium (from Payers)", f"US ${total_prem:,.0f}")
        c2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
        c3.metric("Coverage", f"US ${total_cov:,.0f}")
        c4.metric("Claims", f"US ${total_claims:,.0f}")
        c5.metric("Number of Policies", f"{num_policies}")

        chart_view = st.radio("Chart Type", ["Donor-Style Summary", "Stacked by Pool"], horizontal=True)

        colors = [
            "#e6194B","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#46f0f0",
            "#f032e6","#bcf60c","#fabebe","#008080","#e6beff","#9a6324","#fffac8",
            "#800000","#aaffc3","#808000","#ffd8b1","#000075","#808080"
        ]

        if picked_cols:
            if chart_view == "Donor-Style Summary":
                s = df_pf[picked_cols].sum().reset_index()
                s.columns = ["Payer", "Amount"]
                s["Payer"] = s["Payer"].map(mapping)
                total = s["Amount"].sum() or 1
                s["%"] = s["Amount"] / total * 100
                s["Label"] = s["%"].apply(lambda x: f"{x:.2f}%") + "<br>" + s["Amount"].apply(lambda x: f"${x/1e6:.2f}m")
                fig = px.bar(s, x="Payer", y="Amount", text="Label", color="Payer",
                             title="Premium Contribution by Financiers", template="plotly_white",
                             color_discrete_sequence=colors)
                st.plotly_chart(fig, use_container_width=True)
            else:
                pool_column = "Pool" if st.session_state.get("show_sub_pools") else "Master Pool"
                if pool_column not in df_pf.columns:
                    pool_column = "Master Pool"
                melted = df_pf[[pool_column] + picked_cols].melt(id_vars=pool_column, var_name="Payer", value_name="Amount")
                melted["Payer"] = melted["Payer"].map(mapping)

                all_pools = sort_pools(df[pool_column].dropna().astype(str).unique().tolist()) if pool_column in df.columns else []
                all_payers = melted["Payer"].unique().tolist()
                full = pd.MultiIndex.from_product([all_pools, all_payers], names=[pool_column, "Payer"]).to_frame(index=False)
                grouped_actual = melted.groupby([pool_column, "Payer"], as_index=False)["Amount"].sum()
                grouped = full.merge(grouped_actual, on=[pool_column, "Payer"], how="left").fillna(0)

                fig = px.bar(grouped, x=pool_column, y="Amount", color="Payer",
                             title="Premium Payers per Pool (Stacked)", barmode="stack",
                             text_auto=".2s", template="plotly_white",
                             color_discrete_sequence=colors)
                fig.update_layout(xaxis={"categoryorder": "array", "categoryarray": all_pools})
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Filtered Financing Data")
            export_df = df_pf.copy()
            if "Rate-On-Line" in export_df.columns:
                export_df["Rate-On-Line"] = pd.to_numeric(export_df["Rate-On-Line"], errors="coerce").apply(
                    lambda x: f"{x:.2%}" if pd.notna(x) else ""
                )
            if "Ceding %" in export_df.columns:
                export_df["Ceding %"] = pd.to_numeric(export_df["Ceding %"], errors="coerce").apply(
                    lambda x: f"{x:.2%}" if pd.notna(x) else ""
                )
            for col in export_df.columns:
                if col not in ["Rate-On-Line", "Ceding %", "Premium Loading"]:
                    if pd.api.types.is_numeric_dtype(export_df[col]):
                        export_df[col] = export_df[col].apply(lambda x: f"{x:,.0f}")
            st.dataframe(export_df)

    # ---------- Section 3 ----------
    elif option == "Claim settlement history":
        st.subheader("Claim Settlement Overview")
        total_claims = df_selection.get("Claims", pd.Series(dtype=float)).sum()
        num_claims = df_selection[df_selection.get("Claims", pd.Series(0)) > 0].shape[0] if "Claims" in df_selection.columns else 0
        avg_claim = total_claims / num_claims if num_claims > 0 else 0

        a, b, c, d = st.columns(4)
        a.metric("Total Claims", f"US ${total_claims:,.0f}")
        b.metric("Number of Policies", f"{num_policies}")
        c.metric("Number of Claims", f"{num_claims}")
        d.metric("Avg Claim (per Claim)", f"US ${avg_claim:,.0f}")

        col1, col2, col3 = st.columns(3)

        with col1:
            if "Claims" in df_selection.columns:
                top_pools = df_selection.groupby("Master Pool")["Claims"].sum().sort_values(ascending=False).reset_index()
                fig1 = px.bar(top_pools, x="Claims", y="Master Pool", orientation="h",
                              title="💰 Top Pools by Claims Paid", text="Claims",
                              template="plotly_white", color="Claims")
                fig1.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
                st.plotly_chart(fig1, use_container_width=True)

        with col2:
            needed = {"Policy Years", "Claims", "Premium"}
            if needed.issubset(df_selection.columns):
                trend = df_selection.groupby("Policy Years")[["Claims", "Premium"]].sum().reset_index()
                fig2 = px.area(trend, x="Policy Years", y=["Premium", "Claims"],
                               title="Claims vs Premium Over Time", template="plotly_white")
                st.plotly_chart(fig2, use_container_width=True)

        with col3:
            needed = {"Claims", "Premium"}
            if needed.issubset(df_selection.columns):
                summary = df_selection.groupby("Master Pool").agg({"Claims": "sum", "Premium": "sum"}).reset_index()
                summary["Loss Ratio"] = (summary["Claims"] / summary["Premium"]) * 100
                top_loss = summary[summary["Premium"] > 0].sort_values("Loss Ratio", ascending=False).head(10)
                fig3 = px.bar(top_loss, x="Master Pool", y="Loss Ratio",
                              title="🔥 Pools with Highest Loss Ratios",
                              text="Loss Ratio", template="plotly_white", color="Loss Ratio")
                fig3.update_traces(texttemplate="%{y:.1f}%", textposition="outside")
                fig3.update_layout(yaxis_title="Loss Ratio (%)")
                st.plotly_chart(fig3, use_container_width=True)

        st.markdown("###  Country-Level Summary Map")
        needed = {"Country", "Claims", "Premium"}
        if needed.issubset(df_selection.columns):
            map_metric = st.radio("Select metric to display on map:", ["Claims", "Premium", "Loss Ratio"], horizontal=True)
            stats = df_selection.groupby("Country")[["Claims", "Premium"]].sum().reset_index()
            stats = stats[stats["Premium"] > 0]
            stats["Loss Ratio"] = (stats["Claims"] / stats["Premium"]) * 100

            color_scale = {"Claims": "Reds", "Premium": "Blues", "Loss Ratio": "Oranges"}
            titles = {
                "Claims": "Total Claims by Country",
                "Premium": "Total Premium by Country",
                "Loss Ratio": "Loss Ratio (%) by Country",
            }
            if not stats.empty:
                fig_map = px.choropleth(
                    stats,
                    locations="Country",
                    locationmode="country names",
                    color=map_metric,
                    hover_name="Country",
                    color_continuous_scale=color_scale[map_metric],
                    title=f"🌍 {titles[map_metric]}",
                    template="plotly_white",
                )
                fig_map.update_geos(showcountries=True, showcoastlines=True, showland=True, fitbounds="locations")
                fig_map.update_layout(margin={"r": 0, "t": 50, "l": 0, "b": 0})
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.info("No country-level data available for selected metric.")

        with st.expander(" View Country-Level Table"):
            if needed.issubset(df_selection.columns):
                st.dataframe(stats.sort_values(map_metric, ascending=False) if not stats.empty else pd.DataFrame())

        st.markdown("#### Filtered Claim Data")
        if "Claims" in df_selection.columns:
            export_df = df_selection.copy()
            export_df["Claims"] = pd.to_numeric(export_df["Claims"], errors="coerce").apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else ""
            )
            if "Rate-On-Line" in export_df.columns:
                export_df["Rate-On-Line"] = pd.to_numeric(export_df["Rate-On-Line"], errors="coerce").apply(
                    lambda x: f"{x:.2%}" if pd.notna(x) else ""
                )
            if "Ceding %" in export_df.columns:
                export_df["Ceding %"] = pd.to_numeric(export_df["Ceding %"], errors="coerce").apply(
                    lambda x: f"{x:.2%}" if pd.notna(x) else ""
                )
            for col in export_df.columns:
                if col not in ["Rate-On-Line", "Ceding %", "Premium Loading"]:
                    if pd.api.types.is_numeric_dtype(export_df[col]):
                        export_df[col] = export_df[col].apply(lambda x: f"{x:,.0f}")
            st.dataframe(export_df)


# =========================
#  IIS
# =========================
if Business_Types == "IIS":

    @st.cache_data(show_spinner=False)
    def load_iis_from_sql() -> pd.DataFrame:
        q = "SELECT * FROM dbo.IIS;"
        df = sql_read(q)

        rename_map = {
            "ARC Net Premium": "ARCNetPremium",
            "Facultative Reinsurance Premium": "FacRePremium",
            "Total Payout ($)": "TotalPayout",
            "Other Key Partners": "Partner",
            "Start Date": "StartDate",
        }
        df = df.rename(columns=rename_map)

        for c in ["ARCNetPremium", "FacRePremium", "TotalPayout"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "StartDate" in df.columns:
            df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
        return df

    df = load_iis_from_sql()

    with st.sidebar.expander("🔎 Filters", expanded=True):
        years = sorted(df["StartDate"].dt.year.dropna().unique()) if "StartDate" in df.columns else []
        all_years = st.checkbox("Select All Years", value=True)
        selected_years = st.multiselect("Select Year", options=years, default=years if all_years else [])

        countries = df["Country"].dropna().unique().tolist() if "Country" in df.columns else []
        all_countries = st.checkbox("Select All Countries", value=True)
        selected_country = st.multiselect("Select Country", options=countries, default=countries if all_countries else [])

        partners = df["Partner"].dropna().unique().tolist() if "Partner" in df.columns else []
        all_partners = st.checkbox("Select All Partners", value=True)
        selected_partner = st.multiselect("Select Partner", options=partners, default=partners if all_partners else [])

    filtered_df = df[
        ((df["StartDate"].dt.year.isin(selected_years)) if "StartDate" in df.columns else True)
        & ((df["Country"].isin(selected_country)) if "Country" in df.columns else True)
        & ((df["Partner"].isin(selected_partner)) if "Partner" in df.columns else True)
    ].copy()

    total_arc = filtered_df.get("ARCNetPremium", pd.Series(dtype=float)).sum()
    total_fac = filtered_df.get("FacRePremium", pd.Series(dtype=float)).sum()
    total_payout = filtered_df.get("TotalPayout", pd.Series(dtype=float)).sum()
    denom = (total_arc + total_fac) if (total_arc + total_fac) > 0 else 1
    claims_ratio = total_payout / denom
    num_programmes = filtered_df["Programme Name"].nunique() if "Programme Name" in filtered_df.columns else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💰 ARC Premium", f"${total_arc:,.0f}")
    k2.metric("🛡️ Facultative Premium", f"${total_fac:,.0f}")
    k3.metric("📤 Total Payout", f"${total_payout:,.0f}")
    k4.metric("📊 Claims Ratio", f"{claims_ratio:.2%}")
    k5.metric("📂 Programmes", num_programmes)

    left, right = st.columns(2)

    with left:
        st.markdown("### 📈 Premiums vs Payouts by Country")
        needed = {"Country", "ARCNetPremium", "FacRePremium", "TotalPayout"}
        if needed.issubset(filtered_df.columns):
            country_agg = (
                filtered_df.groupby("Country")[["ARCNetPremium", "FacRePremium", "TotalPayout"]].sum().reset_index()
            )
            fig1 = px.bar(
                country_agg,
                x="Country",
                y=["ARCNetPremium", "FacRePremium", "TotalPayout"],
                barmode="group",
                title="Premiums vs Payouts by Country",
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            country_agg = pd.DataFrame()
            st.info("Missing expected columns to build the country chart.")

    with right:
        st.markdown("### 🏆 Top 5 Partners by ARC Premium")
        needed = {"Partner", "ARCNetPremium"}
        if needed.issubset(filtered_df.columns):
            partner_agg = (
                filtered_df.groupby("Partner")["ARCNetPremium"].sum().nlargest(5).reset_index()
            )
            fig2 = px.bar(partner_agg, x="ARCNetPremium", y="Partner", orientation="h", title="Top 5 Partners")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Missing expected columns to build the partner chart.")

    st.markdown("### 📋 Country Summary Table")
    if not country_agg.empty:
        st.dataframe(country_agg)
        csv = country_agg.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Summary CSV", data=csv, file_name="iis_country_summary.csv", mime="text/csv")
    else:
        st.info("No country summary to display yet.")
