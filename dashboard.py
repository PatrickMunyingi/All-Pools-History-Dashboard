import streamlit as st
import pandas as pd
import plotly.express as px

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

# --- Helper for sorting pools naturally ---
def sort_pools(pool_list):
    return sorted(pool_list, key=lambda x: (int(''.join(filter(str.isdigit, x)) or 0), x))

# --- Load and Clean Data ---
@st.cache_data
def load_data():
    df = pd.read_excel("all pools.xlsx")
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

# --- View Selection ---
option = st.selectbox("What would you like to view?", 
                      ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history"))

# --- Section 1: Premium and Country Info ---
if option == "Premium and country basic Information":
    total_premium = df_selection['Premium'].sum()
    total_claims = df_selection['Claims'].sum()
    total_coverage = df_selection['Coverage'].sum()
    loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Premium", f"US ${total_premium:,.0f}")
    col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
    col3.metric("Coverage", f"US ${total_coverage:,.0f}")
    col4.metric("Claims", f"US ${total_claims:,.0f}")

    col1, col2, col3 = st.columns(3)

    with col1:
        if not df_selection.empty:
            yearly_premium = df_selection.groupby('Policy Years')['Premium'].sum().reset_index()
            fig1 = px.line(yearly_premium, x='Policy Years', y='Premium', markers=True,
                           title='Yearly Premiums Over Time', template='plotly_white')
            st.plotly_chart(fig1)

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
    st.markdown("### Select Premium Payers")
    select_all_payers = st.checkbox("Select All Premium Payers", value=True)
    selected_payers_display = st.multiselect("Premium Payers", premium_payers_mapping.values(), default=premium_payers_mapping.values() if select_all_payers else [])
    selected_payers = [k for k, v in premium_payers_mapping.items() if v in selected_payers_display]

    if not selected_payers:
        df_premium_financing = df_selection
        total_premium = df_premium_financing['Premium'].sum()
    else:
        df_premium_financing = df_selection[df_selection[selected_payers].fillna(0).sum(axis=1) > 0]
        total_premium = df_premium_financing[selected_payers].sum().sum()

    total_claims = df_premium_financing['Claims'].sum()
    total_coverage = df_premium_financing['Coverage'].sum()
    loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Premium", f"US ${total_premium:,.0f}")
    col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
    col3.metric("Coverage", f"US ${total_coverage:,.0f}")
    col4.metric("Claims", f"US ${total_claims:,.0f}")

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
            fig.update_layout(xaxis={'categoryorder':'array', 'categoryarray': all_pools})
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Filtered Financing Data")
        st.dataframe(df_premium_financing)
        csv = df_premium_financing.to_csv(index=False).encode('utf-8')
        st.download_button("Download Financing CSV", csv, "premium_financing.csv", "text/csv")

# --- Section 3: Claim Settlement ---
elif option == "Claim settlement history":
    st.subheader("Claim Settlement Overview")
    total_claims = df_selection['Claims'].sum()
    num_records = len(df_selection)
    avg_claim = total_claims / num_records if num_records > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Claims", f"US ${total_claims:,.0f}")

    col3.metric("Avg Claim", f"US ${avg_claim:,.0f}")

    sorted_all_pools = sort_pools(df[pool_column].unique())
    claims_by_pool = df_selection.groupby(pool_column, as_index=False)["Claims"].sum()
    claims_by_pool = pd.DataFrame({pool_column: sorted_all_pools}).merge(claims_by_pool, on=pool_column, how="left").fillna(0)
    claims_by_pool["Avg Trend"] = claims_by_pool["Claims"].expanding().mean()



    col1, col2 = st.columns(2)
    with col1:
        claims_by_peril = df_selection.groupby("Peril")["Claims"].sum().reset_index()
        fig2 = px.pie(claims_by_peril, names="Peril", values="Claims", title="Claims by Peril", hole=0.5)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        if "Policy Years" in df_selection.columns:
            claims_by_year = df_selection.groupby("Policy Years")["Claims"].sum().reset_index()
            fig3 = px.line(claims_by_year, x="Policy Years", y="Claims", title="Claims Over Policy Years", markers=True, template="plotly_white")
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("#### Filtered Claim Data")
    st.dataframe(df_selection)
    csv = df_selection.to_csv(index=False).encode("utf-8")
    st.download_button("Download Claims", csv, "claim_settlement.csv", "text/csv")
