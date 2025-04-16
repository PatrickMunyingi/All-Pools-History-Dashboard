import pandas as pd
import plotly.express as px
from datetime import datetime
import streamlit as st

# --- Page Setup ---
st.set_page_config(page_title="All Pools History Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- Header Styling ---
st.markdown("""
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
""", unsafe_allow_html=True)

st.markdown("<h1 class='animated-title'>ALL POOLS HISTORY DASHBOARD</h1>", unsafe_allow_html=True)

#Add date info below the animated title
from datetime import datetime
today = datetime.today()
first_of_month = today.replace(day=1).strftime("%B %d, %Y")
st.markdown(f"** Data as of {first_of_month}**")

Business_Types=st.selectbox("Choose Business Type",("","SOVEREIGN BUSINESS","IIS"))
if Business_Types=="SOVEREIGN BUSINESS":
    # --- Helper for sorting pools naturally ---
    def sort_pools(pool_list):
        return sorted(pool_list, key=lambda x: (int(''.join(filter(str.isdigit, x)) or 0), x))

    # --- Load and Clean Data ---
    @st.cache_data
    def load_data():
        df = pd.read_excel("all pools.xlsx",sheet_name="SOV&REPLICA")
        if "Policy ID" in df.columns:
            df.set_index("Policy ID", inplace=True)
        numeric_cols = ['Premium', 'Attachment', 'Exhaustion', 'Coverage', 'Claims']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
        df['Pool'] = df['Pool'].astype(str)
        df['Master Pool'] = df['Pool'].str.extract(r'(\d+)')
        df['Master Pool'] = df['Master Pool'].fillna(df['Pool'])
        return df

    df = load_data()
    premium_payers = [col for col in df.columns if col.startswith("Premium Financed by")]

    # --- Sidebar Filters ---
    with st.sidebar.expander("Filters", expanded=True):
        show_sub_pools = st.checkbox("Show Sub-Pools (like 10A, 10B)", value=False)
        pool_column = 'Pool' if show_sub_pools else 'Master Pool'

        sorted_pool_options = sort_pools(df[pool_column].unique())
        select_all_pools = st.checkbox("Select All Pools", value=True)
        pool = st.multiselect("Select Pool:", options=sorted_pool_options, default=sorted_pool_options if select_all_pools else [])

        select_all_policy_types = st.checkbox("Select All Policy Types", value=True)
        policy_type = st.multiselect("Policy Type:", options=df["Policy Type"].unique(), default=df["Policy Type"].unique() if select_all_policy_types else [])

        select_all_countries = st.checkbox("Select All Countries", value=True)
        country = st.multiselect("Country:", options=df["Country"].unique(), default=df["Country"].unique() if select_all_countries else [])

        select_all_regions = st.checkbox("Select All Regions", value=True)
        region = st.multiselect("Region:", options=df["Region"].unique(), default=df["Region"].unique() if select_all_regions else [])

        select_all_peril = st.checkbox("Select All Perils", value=True)
        peril = st.multiselect("Peril:", options=df["Peril"].unique(), default=df["Peril"].unique() if select_all_peril else [])

    # --- Filter Dataset ---
    df_selection = df[
        df[pool_column].isin(pool) &
        df['Policy Type'].isin(policy_type) &
        df['Country'].isin(country) &
        df['Peril'].isin(peril) &
        df['Region'].isin(region)
    ]
    num_policies = len(df_selection)

    # --- View Selection ---
    option = st.selectbox("What would you like to view?", 
                        ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history"))

    # --- Section 1: Premium and Country Info ---
    if option == "Premium and country basic Information":
        total_premium = df_selection['Premium'].sum()
        total_claims = df_selection['Claims'].sum()
        total_coverage = df_selection['Coverage'].sum()
        loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

        st.subheader("Premium and Country Infomation Overview")

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

                yearly_trend = df_selection.groupby('Policy Years')[trend_metric].sum().reset_index()
                fig1 = px.line(yearly_trend, x='Policy Years', y=trend_metric, markers=True,
                            title=f'Yearly {trend_metric}s Over Time', template='plotly_white')
                st.plotly_chart(fig1, use_container_width=True)

        with col2:
            country_count = df_selection['Country'].value_counts().reset_index()
            country_count.columns = ['Country', 'Count']
            fig2 = px.bar(country_count, x='Count', y='Country', orientation='h', title="Country Count")
            st.plotly_chart(fig2)

        with col3:
            policy_type_counts = df_selection['Policy Type'].value_counts().reset_index()
            policy_type_counts.columns = ['Policy Type', 'Count']
            fig3 = px.pie(policy_type_counts, names='Policy Type', values='Count', hole=0.6, title="Policy Type Distribution")
            st.plotly_chart(fig3)

        st.markdown("### Filtered Data")
        st.dataframe(df_selection)
        csv = df_selection.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "filtered_data.csv", "text/csv")

    # --- Section 2: Premium Financing and Tracker ---
    elif option == "Premium financing and Tracker":
        premium_payers_mapping = {col: col.replace("Premium Financed by ", "") for col in premium_payers}
        st.markdown("##### Select Premium Payers")
        select_all_payers = st.checkbox("Select All Premium Payers", value=True)
        selected_payers_display = st.multiselect("Premium Payers", premium_payers_mapping.values(), default=premium_payers_mapping.values() if select_all_payers else [])
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
        st.subheader("Premium Financing Overview")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Premium (from Payers)", f"US ${total_premium:,.0f}")
        col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
        col3.metric("Coverage", f"US ${total_coverage:,.0f}")
        col4.metric("Claims", f"US ${total_claims:,.0f}")
        col5.metric("Number of Policies", f"{num_policies}")

        chart_view = st.radio("Chart Type", ["Donor-Style Summary", "Stacked by Pool"], horizontal=True)

        if selected_payers:
            if chart_view == "Donor-Style Summary":
                df_summary = df_premium_financing[selected_payers].sum().reset_index()
                df_summary.columns = ['Payer', 'Amount']
                df_summary['Payer'] = df_summary['Payer'].map(premium_payers_mapping)
                df_summary['%'] = (df_summary['Amount'] / df_summary['Amount'].sum()) * 100
                df_summary['Label'] = df_summary['%'].apply(lambda x: f"{x:.2f}%") + "<br>" + df_summary['Amount'].apply(lambda x: f"${x/1e6:.2f}m")
                fig = px.bar(df_summary, x='Payer', y='Amount', text='Label', color='Payer',
                            title='Premium Contribution by Financiers', template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)

            else:
                df_melted = df_premium_financing[[pool_column] + selected_payers].melt(id_vars=pool_column, var_name='Payer', value_name='Amount')
                df_melted['Payer'] = df_melted['Payer'].map(premium_payers_mapping)

                all_pools = sort_pools(df[pool_column].unique())
                all_payers = df_melted['Payer'].unique()
                full_index = pd.MultiIndex.from_product([all_pools, all_payers], names=[pool_column, "Payer"]).to_frame(index=False)

                grouped_actual = df_melted.groupby([pool_column, 'Payer'], as_index=False)['Amount'].sum()
                grouped = full_index.merge(grouped_actual, on=[pool_column, 'Payer'], how='left').fillna(0)

                fig = px.bar(grouped, x=pool_column, y='Amount', color='Payer',
                            title='Premium Payers per Pool (Stacked)', barmode='stack',
                            text_auto='.2s', template='plotly_white')
                fig.update_layout(xaxis={'categoryorder': 'array', 'categoryarray': all_pools})
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Filtered Financing Data")
            st.dataframe(df_premium_financing)
            csv = df_premium_financing.to_csv(index=True).encode('utf-8')
            st.download_button("Download Financing CSV", csv, "premium_financing.csv", "text/csv")

    # --- Section 3: Claim Settlement ---
    elif option == "Claim settlement history":
        st.subheader("Claim Settlement Overview")
        total_claims = df_selection['Claims'].sum()
        num_claims = df_selection[df_selection["Claims"] > 0].shape[0]
        avg_claim = total_claims / num_claims if num_claims > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Claims", f"US ${total_claims:,.0f}")
        col2.metric("Number of Policies", f"{num_policies}")
        col3.metric("Number of Claims", f"{num_claims}")
        col4.metric("Avg Claim (per Claim)", f"US ${avg_claim:,.0f}")

        sorted_all_pools = sort_pools(df[pool_column].unique())
        claims_by_pool = df_selection.groupby(pool_column, as_index=False)["Claims"].sum()
        claims_by_pool = pd.DataFrame({pool_column: sorted_all_pools}).merge(claims_by_pool, on=pool_column, how="left").fillna(0)
        claims_by_pool["Avg Trend"] = claims_by_pool["Claims"].expanding().mean()

        col1, col2,col3 = st.columns(3)
        # 1. Top 10 Pools by Claims
        with col1:
            top_pools = df_selection.groupby(pool_column)["Claims"].sum().sort_values(ascending=False).head(10).reset_index()
            fig1 = px.bar(
                top_pools,
                x="Claims",
                y=pool_column,
                orientation="h",
                title="💰 Top 10 Pools by Claims Paid",
                text="Claims",
                template="plotly_white"
            )
            fig1.update_traces(texttemplate='$%{x:,.0f}', textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)

        # 2. Claims vs Premium Over Time
        with col2:
            claims_trend = df_selection.groupby("Policy Years")[["Claims", "Premium"]].sum().reset_index()
            fig2 = px.area(claims_trend, x="Policy Years", y=["Premium", "Claims"],
                        title=" Claims vs Premium Over Time", template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)

        # 3. Highest Loss Ratios by Pool
        with col3:
            pool_summary = df_selection.groupby(pool_column).agg({'Claims': 'sum', 'Premium': 'sum'}).reset_index()
            pool_summary["Loss Ratio"] = pool_summary["Claims"] / pool_summary["Premium"] * 100
            top_loss = pool_summary[pool_summary["Premium"] > 0].sort_values("Loss Ratio", ascending=False).head(10)

            fig3 = px.bar(
                top_loss,
                x=pool_column,
                y="Loss Ratio",
                title="🔥 Pools with Highest Loss Ratios",
                text="Loss Ratio",
                template="plotly_white"
            )
            fig3.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
            fig3.update_layout(yaxis_title="Loss Ratio (%)")
            st.plotly_chart(fig3, use_container_width=True)

        # 4. Claims by Country - Choropleth Map (full width)
        #  Claims/Premium/Loss Ratio Choropleth Map with Toggle

            # --- Country-Level Choropleth Map (inside Claim Settlement block only) ---
        st.markdown("###  Country-Level Summary Map")

        # Metric selection
        map_metric = st.radio("Select metric to display on map:", ["Claims", "Premium", "Loss Ratio"], horizontal=True)

        # Group & compute base stats
        country_stats = df_selection.groupby("Country")[["Claims", "Premium"]].sum().reset_index()
        country_stats = country_stats[country_stats["Premium"] > 0]  # avoid divide by zero
        country_stats["Loss Ratio"] = (country_stats["Claims"] / country_stats["Premium"]) * 100

        # Choose color scale
        color_scale = {
            "Claims": "Reds",
            "Premium": "Blues",
            "Loss Ratio": "Oranges"
        }

        # Format title
        metric_title = {
            "Claims": "Total Claims by Country",
            "Premium": "Total Premium by Country",
            "Loss Ratio": "Loss Ratio (%) by Country"
        }

        # Plot map
        if not country_stats.empty:
            fig_map = px.choropleth(
                country_stats,
                locations="Country",
                locationmode="country names",
                color=map_metric,
                hover_name="Country",
                color_continuous_scale=color_scale[map_metric],
                title=f"🌍 {metric_title[map_metric]}",
                template="plotly_white"
            )
            fig_map.update_geos(
                showcountries=True,
                showcoastlines=True,
                showland=True,
                fitbounds="locations"
            )
            fig_map.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No country-level data available for selected metric.")

        # Optional table below
        with st.expander(" View Country-Level Table"):
            st.dataframe(country_stats.sort_values(map_metric, ascending=False))



        st.markdown("#### Filtered Claim Data")
        st.dataframe(df_selection)
        csv = df_selection.to_csv(index=False).encode("utf-8")
        st.download_button("Download Claims",csv, "claim_settlement.pdf", "pdf/csv")


if Business_Types=="IIS":
    @st.cache_data
    def load_data():
        df = pd.read_excel("all pools.xlsx", sheet_name="IIS")
        return df

    df = load_data()

    # --- Data Cleaning ---
    df.columns = df.columns.str.strip().str.replace(" ", "", regex=False)
    df = df.rename(columns={
        "ARC Net Premium": "ARCNetPremium",
        "Facultative Reinsurance Premium": "FacRePremium",
        "Total Payout ($)": "TotalPayout",
        "Other Key Partners": "Partner",
        "Country": "Country",
        "Start Date": "StartDate"
    })
    df[["ARCNetPremium", "FacRePremium", "TotalPayout"]] = df[["ARCNetPremium", "FacRePremium", "TotalPayout"]].apply(pd.to_numeric, errors='coerce')
    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")

    # --- Filters ---
    with st.sidebar.expander("🔎 Filters", expanded=True):
        # Year filter with select all
        year_list = sorted(df["StartDate"].dt.year.dropna().unique())
        select_all_years = st.checkbox("Select All Years", value=True)
        selected_years = st.multiselect("Select Year", options=year_list,
                                        default=year_list if select_all_years else [])

        # Country filter with select all
        country_list = df["Country"].dropna().unique()
        select_all_countries = st.checkbox("Select All Countries", value=True)
        selected_country = st.multiselect("Select Country", options=country_list,
                                          default=country_list if select_all_countries else [])

        # Partner filter with select all
        partner_list = df["Partner"].dropna().unique()
        select_all_partners = st.checkbox("Select All Partners", value=True)
        selected_partner = st.multiselect("Select Partner", options=partner_list,
                                          default=partner_list if select_all_partners else [])

    # --- Filtered Data ---
    filtered_df = df[
        (df["StartDate"].dt.year.isin(selected_years)) &
        (df["Country"].isin(selected_country)) &
        (df["Partner"].isin(selected_partner))
    ]

    # --- KPIs ---
    total_arc = filtered_df["ARCNetPremium"].sum()
    total_fac = filtered_df["FacRePremium"].sum()
    total_payout = filtered_df["TotalPayout"].sum()
    claims_ratio = total_payout / (total_arc + total_fac) if (total_arc + total_fac) > 0 else 0
    num_programmes = filtered_df["Programme Name"].nunique()

    st.markdown("## 📊 Inclusive Insurance Business (IIS) Dashboard")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("💰 ARC Premium", f"${total_arc:,.0f}")
    kpi2.metric("🛡️ Facultative Premium", f"${total_fac:,.0f}")
    kpi3.metric("📤 Total Payout", f"${total_payout:,.0f}")
    kpi4.metric("📊 Claims Ratio", f"{claims_ratio:.2%}")
    kpi5.metric("📂 Programmes", num_programmes)

    # --- Visuals ---
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("### 📈 Premiums vs Payouts by Country")
        country_agg = filtered_df.groupby("Country")[["ARCNetPremium", "FacRePremium", "TotalPayout"]].sum().reset_index()
        fig1 = px.bar(country_agg, x="Country", y=["ARCNetPremium", "FacRePremium", "TotalPayout"],
                      barmode="group", title="Premiums vs Payouts by Country")
        st.plotly_chart(fig1, use_container_width=True)

    with right_col:
        st.markdown("### 🏆 Top 5 Partners by ARC Premium")
        partner_agg = filtered_df.groupby("Partner")["ARCNetPremium"].sum().nlargest(5).reset_index()
        fig2 = px.bar(partner_agg, x="ARCNetPremium", y="Partner", orientation="h", title="Top 5 Partners")
        st.plotly_chart(fig2, use_container_width=True)

    # --- Summary Table and Download ---
    st.markdown("### 📋 Country Summary Table")
    st.dataframe(country_agg)

    csv = country_agg.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download Summary CSV", data=csv, file_name="iis_country_summary.csv", mime="text/csv")
