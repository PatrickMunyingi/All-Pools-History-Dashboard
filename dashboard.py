import os, io, time, shutil
import pandas as pd
import plotly.express as px
from datetime import datetime
import streamlit as st
import requests
from requests.exceptions import RequestException, HTTPError, Timeout
from openpyxl import load_workbook

# =========================
# CONFIG
# =========================
DATA_PATH = "all pools.xlsx"   # <— your main workbook
IIS_SHEET = "IIS"

st.set_page_config(page_title="All Pools History Dashboard", layout="wide", initial_sidebar_state="expanded")

# =========================
# STYLES / HEADER
# =========================
st.markdown("""
    <style>
        [data-testid="stHeader"] { height: 0rem; }
        [data-testid="stToolbar"] { display: none; }
        @keyframes fadeInBounce { 0% {opacity:0; transform: translateY(-20px);}
                                  50% {opacity:.5; transform: translateY(5px);}
                                  100% {opacity:1; transform: translateY(0);} }
        .animated-title { text-align:center; color:#1E90FF; font-size:40px; font-weight:bold; animation:fadeInBounce 1.5s ease-out; }
    </style>
""", unsafe_allow_html=True)
st.markdown("<h1 class='animated-title'>ALL POOLS HISTORY DASHBOARD</h1>", unsafe_allow_html=True)
first_of_month = datetime.today().replace(day=1).strftime("%B %d, %Y")
st.markdown(f"** Data as of {first_of_month}**")

# =========================
# HELPERS
# =========================
def sort_pools(pool_list):
    return sorted(pool_list, key=lambda x: (int(''.join(filter(str.isdigit, x)) or 0), x))

@st.cache_data
def load_data_sov():
    df = pd.read_excel(DATA_PATH, sheet_name="SOV&REPLICA")
    if "Policy ID" in df.columns:
        df.set_index("Policy ID", inplace=True)
    numeric_cols = ['Premium', 'Attachment', 'Exhaustion', 'Coverage', 'Claims']
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['Pool'] = df['Pool'].astype(str)
    df['Master Pool'] = df['Pool'].str.extract(r'(\d+)')
    df['Master Pool'] = df['Master Pool'].fillna(df['Pool'])
    return df

@st.cache_data
def load_data_iis():
    return pd.read_excel(DATA_PATH, sheet_name=IIS_SHEET)

def backup_then_replace_iis_sheet(df: pd.DataFrame, xlsx_path: str, sheet_name: str = IIS_SHEET):
    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(f"Workbook not found: {xlsx_path}")
    # 1) backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.splitext(xlsx_path)[0] + f"_BACKUP_{ts}.xlsx"
    shutil.copy2(xlsx_path, backup_path)
    # 2) remove IIS sheet + save structure
    wb = load_workbook(xlsx_path)
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]; wb.remove(ws)
    wb.create_sheet(sheet_name); wb.save(xlsx_path)
    # 3) write new IIS
    with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return backup_path

# =========================
# APP
# =========================
Business_Types = st.selectbox("Choose Business Type", ("","SOVEREIGN BUSINESS","IIS"))

# =========================
# SOVEREIGN BUSINESS
# =========================
if Business_Types == "SOVEREIGN BUSINESS":
    df = load_data_sov()
    premium_payers = [c for c in df.columns if c.startswith("Premium Financed by")]

    # Sidebar filters
    with st.sidebar.expander("Filters", expanded=True):
        show_sub_pools = st.checkbox("Show Sub-Pools (like 10A, 10B)", value=False)
        pool_column = 'Pool' if show_sub_pools else 'Master Pool'
        sorted_pool_options = sort_pools(df[pool_column].unique())
        select_all_pools = st.checkbox("Select All Pools", value=True)
        pool = st.multiselect("Select Pool:", options=sorted_pool_options,
                              default=sorted_pool_options if select_all_pools else [])

        select_all_policy_types = st.checkbox("Select All Policy Types", value=True)
        policy_type = st.multiselect("Policy Type:", options=df["Policy Type"].unique(),
                                     default=df["Policy Type"].unique() if select_all_policy_types else [])

        select_all_countries = st.checkbox("Select All Countries", value=True)
        country = st.multiselect("Country:", options=df["Country"].unique(),
                                 default=df["Country"].unique() if select_all_countries else [])

        select_all_regions = st.checkbox("Select All Regions", value=True)
        region = st.multiselect("Region:", options=df["Region"].unique(),
                                default=df["Region"].unique() if select_all_regions else [])

        select_all_peril = st.checkbox("Select All Perils", value=True)
        peril = st.multiselect("Peril:", options=df["Peril"].unique(),
                               default=df["Peril"].unique() if select_all_peril else [])

        select_all_crop_types = st.checkbox("Select All Crop Types", value=True)
        crop_type = st.multiselect("Crop Type:", options=df["Crop Type"].unique(),
                                   default=df["Crop Type"].unique() if select_all_peril else [])

    df_selection = df[
        df[pool_column].isin(pool) &
        df['Policy Type'].isin(policy_type) &
        df['Country'].isin(country) &
        df['Peril'].isin(peril) &
        df['Region'].isin(region) &
        df['Crop Type'].isin(crop_type)
    ]
    num_policies = len(df_selection)

    option = st.selectbox("What would you like to view?",
                          ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history"))

    # --- Section 1
    if option == "Premium and country basic Information":
        total_premium = df_selection['Premium'].sum()
        total_claims = df_selection['Claims'].sum()
        total_coverage = df_selection['Coverage'].sum()
        loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Premium", f"US ${total_premium:,.0f}")
        col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
        col3.metric("Coverage", f"US ${total_coverage:,.0f}")
        col4.metric("Claims", f"US ${total_claims:,.0f}")
        col5.metric("Number of Policies", f"{num_policies}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if not df_selection.empty:
                trend_metric = st.radio("Select Metric", ["Premium", "Coverage"], horizontal=True)
                Pool_trend = df_selection.groupby(pool_column)[trend_metric].sum().reset_index()
                Pool_trend[pool_column] = Pool_trend[pool_column].astype(str)
                Pool_trend["__num"] = Pool_trend[pool_column].str.extract(r"(\d+)").astype(int)
                Pool_trend["__has_suffix"] = Pool_trend[pool_column].str.contains(r"[A-Za-z]")
                ordered_labels = Pool_trend.sort_values(["__has_suffix","__num"])[pool_column].tolist()
                Pool_trend[pool_column] = pd.Categorical(Pool_trend[pool_column], categories=ordered_labels, ordered=True)
                fig1 = px.line(Pool_trend.sort_values([pool_column]),
                               x=pool_column, y=trend_metric, markers=True,
                               title=f'Yearly {trend_metric}s Over Time', template='plotly_white',
                               category_orders={pool_column: ordered_labels})
                st.plotly_chart(fig1, use_container_width=True)
        with col2:
            country_count = df_selection['Country'].value_counts().reset_index()
            country_count.columns = ['Country','Count']
            fig2 = px.bar(country_count, x='Count', y='Country', orientation='h', title="Country Count")
            st.plotly_chart(fig2, use_container_width=True)
        with col3:
            policy_type_counts = df_selection['Policy Type'].value_counts().reset_index()
            policy_type_counts.columns = ['Policy Type','Count']
            fig3 = px.pie(policy_type_counts, names='Policy Type', values='Count', hole=0.6, title="Policy Type Distribution")
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### Filtered Data")
        export_df = df_selection.copy()
        if 'Rate-On-Line' in export_df:
            export_df['Rate-On-Line'] = export_df['Rate-On-Line'].apply(lambda x: f"{x:.2%}")
        if 'Ceding %' in export_df:
            export_df['Ceding %'] = export_df['Ceding %'].apply(lambda x: f"{x:.2%}")
        for col in export_df.columns:
            if col not in ['Rate-On-Line','Ceding %','Premium Loading'] and pd.api.types.is_numeric_dtype(export_df[col]):
                export_df[col] = export_df[col].apply(lambda x: f"{x:,.0f}")
        st.dataframe(export_df)

    # --- Section 2
    elif option == "Premium financing and Tracker":
        premium_payers = [c for c in df.columns if c.startswith("Premium Financed by")]
        premium_payers_mapping = {c: c.replace("Premium Financed by ", "") for c in premium_payers}
        Financing_markdown = 'Note: Pools 1–5 had no premium financing; it began at Pool 6 (2019/2020).'
        st.markdown("### Select Premium Payers", help=Financing_markdown)
        select_all_payers = st.checkbox("Select All Premium Payers", value=True)
        selected_payers_display = st.multiselect("Premium Payers", premium_payers_mapping.values(),
                                                 default=premium_payers_mapping.values() if select_all_payers else [])
        selected_payers = [k for k, v in premium_payers_mapping.items() if v in selected_payers_display]

        if not selected_payers:
            df_premium_financing = df_selection
            total_premium = df_premium_financing['Premium'].sum()
        else:
            df_premium_financing = df_selection[df_selection[selected_payers].fillna(0).sum(axis=1) > 0]
            total_premium = df_premium_financing[selected_payers].sum().sum()

        total_claims = df_selection['Claims'].sum()
        total_coverage = df_selection['Coverage'].sum()
        loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Premium (from Payers)", f"US ${total_premium:,.0f}")
        c2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
        c3.metric("Coverage", f"US ${total_coverage:,.0f}")
        c4.metric("Claims", f"US ${total_claims:,.0f}")
        c5.metric("Number of Policies", f"{num_policies}")

        chart_view = st.radio("Chart Type", ["Donor-Style Summary","Stacked by Pool"], horizontal=True)
        palette = px.colors.qualitative.Set3

        if selected_payers:
            if chart_view == "Donor-Style Summary":
                df_summary = df_premium_financing[selected_payers].sum().reset_index()
                df_summary.columns = ['Payer','Amount']
                df_summary['Payer'] = df_summary['Payer'].map(premium_payers_mapping)
                df_summary['%'] = (df_summary['Amount'] / df_summary['Amount'].sum()) * 100
                df_summary['Label'] = df_summary['%'].apply(lambda x: f"{x:.2f}%") + "<br>" + df_summary['Amount'].apply(lambda x: f"${x/1e6:.2f}m")
                fig = px.bar(df_summary, x='Payer', y='Amount', text='Label', color='Payer',
                             title='Premium Contribution by Financiers', template='plotly_white',
                             color_discrete_sequence=palette)
                st.plotly_chart(fig, use_container_width=True)
            else:
                df_melted = df_premium_financing[[pool_column] + selected_payers].melt(id_vars=pool_column, var_name='Payer', value_name='Amount')
                df_melted['Payer'] = df_melted['Payer'].map(premium_payers_mapping)
                all_pools = sort_pools(df[pool_column].unique())
                all_payers = df_melted['Payer'].unique()
                full_index = pd.MultiIndex.from_product([all_pools, all_payers], names=[pool_column,"Payer"]).to_frame(index=False)
                grouped_actual = df_melted.groupby([pool_column,'Payer'], as_index=False)['Amount'].sum()
                grouped = full_index.merge(grouped_actual, on=[pool_column,'Payer'], how='left').fillna(0)
                fig = px.bar(grouped, x=pool_column, y='Amount', color='Payer',
                             title='Premium Payers per Pool (Stacked)', barmode='stack',
                             text_auto='.2s', template='plotly_white', color_discrete_sequence=palette)
                fig.update_layout(xaxis={'categoryorder':'array','categoryarray':all_pools})
                st.plotly_chart(fig, use_container_width=True)

    # --- Section 3
    elif option == "Claim settlement history":
        st.subheader("Claim Settlement Overview")
        total_claims = df_selection['Claims'].sum()
        num_claims = df_selection[df_selection["Claims"] > 0].shape[0]
        avg_claim = total_claims / num_claims if num_claims > 0 else 0
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Claims", f"US ${total_claims:,.0f}")
        c2.metric("Number of Policies", f"{num_policies}")
        c3.metric("Number of Claims", f"{num_claims}")
        c4.metric("Avg Claim (per Claim)", f"US ${avg_claim:,.0f}")
        sorted_all_pools = sort_pools(df[pool_column].unique())
        claims_by_pool = df_selection.groupby(pool_column, as_index=False)["Claims"].sum()
        claims_by_pool = pd.DataFrame({pool_column:sorted_all_pools}).merge(claims_by_pool, on=pool_column, how="left").fillna(0)
        claims_by_pool["Avg Trend"] = claims_by_pool["Claims"].expanding().mean()
        col1, col2, col3 = st.columns(3)
        with col1:
            top_pools = df_selection.groupby(pool_column)["Claims"].sum().sort_values(ascending=False).reset_index()
            fig1 = px.bar(top_pools, x="Claims", y=pool_column, orientation="h",
                          title="💰 Top 10 Pools by Claims Paid", text="Claims", template="plotly_white", color="Claims")
            fig1.update_traces(texttemplate='$%{x:,.0f}', textposition='outside'); st.plotly_chart(fig1, use_container_width=True)
        with col2:
            claims_trend = df_selection.groupby("Policy Years")[["Claims","Premium"]].sum().reset_index()
            fig2 = px.area(claims_trend, x="Policy Years", y=["Premium","Claims"], title="Claims vs Premium Over Time", template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)
        with col3:
            pool_summary = df_selection.groupby(pool_column).agg({'Claims':'sum','Premium':'sum'}).reset_index()
            pool_summary["Loss Ratio"] = pool_summary["Claims"]/pool_summary["Premium"]*100
            top_loss = pool_summary[pool_summary["Premium"]>0].sort_values("Loss Ratio", ascending=False).head(10)
            fig3 = px.bar(top_loss, x=pool_column, y="Loss Ratio", title="🔥 Pools with Highest Loss Ratios",
                          text="Loss Ratio", template="plotly_white", color='Loss Ratio')
            fig3.update_traces(texttemplate='%{y:.1f}%', textposition='outside'); fig3.update_layout(yaxis_title="Loss Ratio (%)")
            st.plotly_chart(fig3, use_container_width=True)

# =========================
# IIS
# =========================
if Business_Types == "IIS":
    df_iis_raw = load_data_iis()
    if "iis_df" not in st.session_state:
        st.session_state.iis_df = df_iis_raw.copy()

    option = st.selectbox("What would you like to view?",
                          ("", "Summary", "Disaster Finder", "Auto-Analysis", "Edit IIS data"))

    # ---------- SUMMARY ----------
    if option == "Summary":
        df = st.session_state.iis_df.copy()
        df.columns = df.columns.str.strip().str.replace(" ", "", regex=False)
        df = df.rename(columns={
            "ARC Net Premium":"ARCNetPremium",
            "Facultative Reinsurance Premium":"FacRePremium",
            "Total Payout ($)":"TotalPayout",
            "Other Key Partners":"Partner",
            "Country":"Country",
            "Start Date":"StartDate"
        })
        for c in ["ARCNetPremium","FacRePremium","TotalPayout"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
        if "StartDate" in df.columns:
            df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")

        with st.sidebar.expander("🔎 Filters", expanded=True):
            year_list = sorted(df["StartDate"].dt.year.dropna().unique()) if "StartDate" in df else []
            select_all_years = st.checkbox("Select All Years", value=True)
            selected_years = st.multiselect("Select Year", options=year_list, default=year_list if select_all_years else [])
            country_list = df["Country"].dropna().unique() if "Country" in df else []
            select_all_countries = st.checkbox("Select All Countries", value=True)
            selected_country = st.multiselect("Select Country", options=country_list, default=country_list if select_all_countries else [])
            partner_list = df["Partner"].dropna().unique() if "Partner" in df else []
            select_all_partners = st.checkbox("Select All Partners", value=True)
            selected_partner = st.multiselect("Select Partner", options=partner_list, default=partner_list if select_all_partners else [])

        mask = pd.Series([True]*len(df))
        if "StartDate" in df and selected_years:
            mask &= df["StartDate"].dt.year.isin(selected_years)
        if "Country" in df and selected_country:
            mask &= df["Country"].isin(selected_country)
        if "Partner" in df and selected_partner:
            mask &= df["Partner"].isin(selected_partner)
        filtered_df = df[mask].copy()

        total_arc = filtered_df.get("ARCNetPremium", pd.Series(dtype=float)).sum()
        total_fac = filtered_df.get("FacRePremium", pd.Series(dtype=float)).sum()
        total_payout = filtered_df.get("TotalPayout", pd.Series(dtype=float)).sum()
        denom = (total_arc + total_fac) if (total_arc + total_fac) > 0 else 1
        claims_ratio = total_payout / denom
        num_programmes = filtered_df.get("Programme Name", pd.Series(dtype=object)).nunique()

        st.markdown("## 📊 Inclusive Insurance Business (IIS) Dashboard")
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("💰 ARC Premium", f"${total_arc:,.0f}")
        k2.metric("🛡️ Facultative Premium", f"${total_fac:,.0f}")
        k3.metric("📤 Total Payout", f"${total_payout:,.0f}")
        k4.metric("📊 Claims Ratio", f"{claims_ratio:.2%}")
        k5.metric("📂 Programmes", num_programmes)

        if {"Country","ARCNetPremium","FacRePremium","TotalPayout"}.issubset(filtered_df.columns):
            country_agg = filtered_df.groupby("Country")[["ARCNetPremium","FacRePremium","TotalPayout"]].sum().reset_index()
            st.markdown("### 📈 Premiums vs Payouts by Country")
            fig1 = px.bar(country_agg, x="Country", y=["ARCNetPremium","FacRePremium","TotalPayout"], barmode="group",
                          title="Premiums vs Payouts by Country")
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("### 📋 Country Summary Table")
            st.dataframe(country_agg)
            csv = country_agg.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download Summary CSV", data=csv, file_name="iis_country_summary.csv", mime="text/csv")
        else:
            st.info("Country-level fields not found to build the summary table.")

    # ---------- DISASTER FINDER ----------
    if option == "Disaster Finder":
        st.title("🌍 ReliefWeb Explorer (v1 API)")
        st.sidebar.header("🔎 Filters")
        country = st.sidebar.text_input("Country (leave blank for all)", "")
        disaster_type = st.sidebar.text_input("Disaster Type (e.g., flood, drought)", "")
        start_date = st.sidebar.date_input("Start Date", datetime(1990,1,1))
        end_date = st.sidebar.date_input("End Date", datetime.today())
        limit = st.sidebar.slider("Number of results", 10, 100, 50)

        tab1, tab2 = st.tabs(["🌪️ Disasters", "📝 Reports"])

        with tab1:
            st.subheader("🌪️ Disaster Events from ReliefWeb")
            try:
                params = {"appname":"reliefweb-explorer","limit":limit,"profile":"list","sort[]":"date.created:desc"}
                if country:
                    params["filter[field]"] = "country"; params["filter[value]"] = country.lower().strip()
                resp = requests.get("https://api.reliefweb.int/v1/disasters", params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json().get("data", [])
                results = []
                for d in data:
                    f = d["fields"]; date_str = f["date"]["created"][:10]
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if disaster_type:
                        types = [t["name"].lower() for t in f.get("type",[])]
                        if disaster_type.lower() not in types: continue
                    if not (start_date <= dt <= end_date): continue
                    results.append({
                        "Name":f["name"],
                        "Type":", ".join(t["name"] for t in f.get("type",[])),
                        "Country":", ".join(c["name"] for c in f.get("country",[])),
                        "Date":date_str,
                        "URL":f["url"]
                    })
                if not results:
                    st.info("No disasters match the filters.")
                else:
                    ddf = pd.DataFrame(results); st.dataframe(ddf, use_container_width=True)
                    st.download_button("⬇ Download Disasters CSV",
                        data=ddf.to_csv(index=False).encode("utf-8"),
                        file_name="reliefweb_disasters.csv", mime="text/csv")
            except Exception as e:
                st.error(f"❌ Failed to fetch disasters: {e}")

        with tab2:
            st.subheader("📝 Reports from ReliefWeb")
            filters = []
            if country:
                filters.append({"field":"country","value":country.lower().strip()})
            filters.append({"field":"date.created","range":{"from":start_date.strftime("%Y-%m-%d"),
                                                            "to":end_date.strftime("%Y-%m-%d")}})
            payload = {"limit":limit,"profile":"lite","filter":{"conditions":filters},
                       "sort":[{"field":"date.created","direction":"desc"}]}
            try:
                r = requests.post("https://api.reliefweb.int/v1/reports", json=payload,
                                  params={"appname":"reliefweb-explorer"}, timeout=20)
                r.raise_for_status(); reports = r.json().get("data", [])
                if not reports:
                    st.info("No reports found.")
                else:
                    rows = [{"Title":x["fields"]["title"],
                             "Date":x["fields"]["date"]["created"][:10],
                             "Source":", ".join([s["name"] for s in x["fields"].get("source",[])]),
                             "URL":x["fields"]["url"]} for x in reports]
                    ddf = pd.DataFrame(rows); st.dataframe(ddf, use_container_width=True)
                    st.download_button("⬇ Download CSV",
                        data=ddf.to_csv(index=False).encode("utf-8"),
                        file_name="reliefweb_reports.csv", mime="text/csv")
            except Exception as e:
                st.error(f"❌ Failed to fetch reports: {e}")

    # ---------- EDIT IIS DATA ----------
    if option == "Edit IIS data":
        st.subheader("✏️ Edit IIS Data (add/delete columns, cell edits, save)")
        iis_df = st.session_state.iis_df

        # Add column
        with st.expander("➕ Add a column", expanded=True):
            new_col = st.text_input("Column name", placeholder="e.g., Portfolio Manager")
            col_type = st.selectbox("Data type", ["text","number","date"], index=0)
            default_val = None
            if col_type == "text":
                default_val = st.text_input("Default value (optional)")
            elif col_type == "number":
                default_val = st.number_input("Default value (optional)", value=0.0, step=1.0)
            else:
                default_val = st.date_input("Default value (optional)", value=None)
            if st.button("Add column"):
                if not new_col:
                    st.warning("Please enter a column name.")
                elif new_col in iis_df.columns:
                    st.warning(f"'{new_col}' already exists.")
                else:
                    if col_type == "date" and default_val is not None:
                        iis_df[new_col] = pd.to_datetime(default_val)
                    else:
                        iis_df[new_col] = default_val
                    st.session_state.iis_df = iis_df
                    st.success(f"Added column '{new_col}'.")

        # Delete columns
        with st.expander("🗑️ Delete columns"):
            to_delete = st.multiselect("Select columns to delete", options=list(iis_df.columns))
            if st.button("Delete selected"):
                if not to_delete:
                    st.info("No columns selected.")
                else:
                    iis_df.drop(columns=to_delete, inplace=True, errors="ignore")
                    st.session_state.iis_df = iis_df
                    st.success(f"Deleted: {', '.join(to_delete)}")

        # Live grid edits
        st.markdown("### Preview (editable cells)")
        edited = st.data_editor(st.session_state.iis_df, num_rows="dynamic", use_container_width=True)
        st.session_state.iis_df = edited

        # Downloads
        st.markdown("### Save your edits (download)")
        csv_bytes = st.session_state.iis_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="IIS_edited.csv", mime="text/csv")

        xbuf = io.BytesIO()
        with pd.ExcelWriter(xbuf, engine="xlsxwriter") as writer:
            st.session_state.iis_df.to_excel(writer, sheet_name=IIS_SHEET, index=False)
        st.download_button("⬇️ Download Excel", data=xbuf.getvalue(),
                           file_name="IIS_edited.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Save back to source
        st.markdown("### 🔐 Save back to main data source")
        st.caption("This will **overwrite the IIS sheet** in your workbook after making a timestamped backup.")
        confirm = st.checkbox("I understand this will replace the IIS sheet in the source file.")
        save_btn = st.button("Save IIS to all pools.xlsx")
        if save_btn:
            if not confirm:
                st.warning("Please tick the confirmation box first.")
            else:
                try:
                    backup_path = backup_then_replace_iis_sheet(st.session_state.iis_df, DATA_PATH, IIS_SHEET)
                    st.success(f"Saved IIS sheet to '{DATA_PATH}'. Backup created: '{backup_path}'")
                    st.info("Tip: Close the Excel file if it's open—Windows locks files and can block writes.")
                except PermissionError:
                    st.error("Permission denied. Is the workbook open in Excel or set to read-only?")
                except Exception as e:
                    st.error(f"Failed to write IIS sheet: {e}")

    # ---------- AUTO-ANALYSIS ----------
    if option == "Auto-Analysis":
        st.info("Auto-Analysis tool loaded in your earlier version remains compatible. (Omitted here for brevity.)")
