import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="All Pools History Dashboard", layout="wide", initial_sidebar_state="expanded")

# Hide default title
st.markdown("""
    <style>
        header {visibility: hidden;}
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

# Custom animated title
st.markdown("<h1 class='animated-title'>📊 ALL POOLS HISTORY DASHBOARD 🔍💡</h1>", unsafe_allow_html=True)



# Cache Data Loading
@st.cache_data
def load_data():
    return pd.read_excel("all pools.xlsx")  # Load only needed columns if applicable

df = load_data()

# Ensure numerical columns are properly formatted
numeric_cols = ['Premium', 'Attachment', 'Exhaustion', 'Coverage', 'Claims']
df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

#Detect all premiums payers. Colums start with"Premium Paid by"
premium_payers = [col for col in df.columns if col.startswith("Premium Financed by")] 

# Sidebar Filters
with st.sidebar.expander("Filters", expanded=True):
    select_all_pools = st.checkbox("Select All Pools", value=True)
    pool = st.multiselect("Select the Pool:", options=df["Pool"].unique(), default=df["Pool"].unique() if select_all_pools else [])

    select_all_policy_types = st.checkbox("Select All Policy Types", value=True)
    policy_type = st.multiselect("Select the Policy Type:", options=df["Policy Type"].unique(), default=df["Policy Type"].unique() if select_all_policy_types else [])

    select_all_countries = st.checkbox("Select All Countries", value=True)
    country = st.multiselect("Select the Preferred Country:", options=df["Country"].unique(), default=df["Country"].unique() if select_all_countries else [])

    select_all_regions = st.checkbox("Select All Regions", value=True)
    region = st.multiselect("Select Preferred Region:", options=df["Region"].unique(), default=df["Region"].unique() if select_all_regions else [])

    select_all_peril= st.checkbox("Select Perils", value=True)
    peril= st.multiselect("Select Preferred Peril:", options=df["Peril"].unique(), default=df["Peril"].unique() if select_all_peril else [])
    
    
    
# Filtering
df_selection = df[
    df['Policy Type'].isin(policy_type) & 
    df['Pool'].isin(pool) & 
    df['Country'].isin(country) & 
    df['Peril'].isin(peril) &
    df['Region'].isin(region)
]

# Main Page
st.markdown('##')

option = st.selectbox("What would you like to view?", 
                      ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history", "Re-Insurance Information"))

if option == "Premium and country basic Information":
    # KPI Calculations
    total_premium = df_selection['Premium'].sum()
    total_claims = df_selection['Claims'].sum()
    total_coverage = df_selection['Coverage'].sum()
    loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0
    #RoL=df_selection['Rate-On-Line'].mean()

    #Display Metrics
    col1, col2, col3, col4= st.columns(4)
    col1.metric("Total Premium", f"US ${total_premium:,.0f}")
    col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
    col3.metric("Total Coverage", f"US ${total_coverage:,.0f}")
    col4.metric("Total Claims", f"US ${total_claims:,.0f}")
    #col5.metric("Average ROL",f"{RoL:.2f}%")

    # Custom CSS for alignment
    st.markdown(
    """ 
    <style>
    div[data-testid="metric-container"] {
        text-align: center !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stMetricLabel"] {
        text-align: center !important;
        font-size: 26px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: bold !important;
        color: #305D26 !important;
    }
    </style>
    """,
    
    unsafe_allow_html=True
)




    # Charts
    col1, col2, col3 = st.columns(3)

    with col1:
        if 'Policy Years' in df_selection.columns and not df_selection.empty:
            yearly_premium = df_selection.groupby('Policy Years')['Premium'].sum().reset_index()
            plot1 = px.line(yearly_premium, x='Policy Years', y='Premium', markers=True, 
                            title='Yearly Pool Progression of Premiums', template='plotly_white', color_discrete_sequence=["#305D26"])
            st.plotly_chart(plot1)
        else:
            st.warning("No available data for Policy Years.")

    with col2:
        if 'Country' in df_selection.columns and not df_selection.empty:
            country_count = df_selection['Country'].value_counts().reset_index()
            country_count.columns = ['Country', 'Count']
            plot2 = px.bar(country_count, x='Count', y='Country', orientation='h', title="Country Count")
            st.plotly_chart(plot2)
        else:
            st.warning("No country data available.")

    with col3:
        if 'Policy Type' in df_selection.columns and not df_selection.empty:
            policy_type_counts = df_selection['Policy Type'].value_counts().reset_index()
            policy_type_counts.columns = ['Policy Type', 'Count']
            pie_chart = px.pie(policy_type_counts, names='Policy Type', values='Count', hole=0.6, title="Policy Type Distribution",color_discrete_sequence=["#FF9999", "#99CCFF"])
            st.plotly_chart(pie_chart)
        else:
            st.warning("No policy type data available.")

    # Display Filtered Data Table with Export Option
    if not df_selection.empty:
        st.write(f"Showing {len(df_selection)} records.")
        st.dataframe(df_selection)
        csv = df_selection.to_csv(index=False).encode('utf-8')
        st.download_button("Download Data as CSV", csv, "filtered_data.csv", "text/csv")
    



# ✅ Option 2: Premium financing and Tracker
elif option == "Premium financing and Tracker":
    # Premium Payer Selection
    premium_payers_mapping = {col: col.replace("Premium Financed by ", "") for col in premium_payers}

    # Create a container for the premium payer filter at the top
    with st.container():
        st.markdown("### Select Premium Payers")
        premium_payers_mapping = {col: col.replace("Premium Financed by ", "") for col in premium_payers}
        select_all_payers = st.checkbox("Select All Premium Payers", value=True)
        selected_payers_display = st.multiselect(
            "Select Premium Payers", 
            options=premium_payers_mapping.values(), 
            default=premium_payers_mapping.values() if select_all_payers else []
        )
   

    selected_payers = [orig_col for orig_col, display_name in premium_payers_mapping.items() if display_name in selected_payers_display]
    
    # ✅ FIX: If No Payers Selected, Show ALL Data
    if not selected_payers:
        df_premium_financing = df_selection  # Show all unfiltered data
        total_premium = df_premium_financing['Premium'].sum()  # Sum from main column if no filter
    else:
        df_premium_financing = df_selection[df_selection[selected_payers].fillna(0).sum(axis=1) > 0]  # Filter by payers
        total_premium = df_premium_financing[selected_payers].sum().sum()  # ✅ Sum from selected payers

    # ✅ Claims, Coverage, Loss Ratio
    total_claims = df_premium_financing['Claims'].sum()
    total_coverage = df_premium_financing['Coverage'].sum()
    loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

    # Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Premium (from Payers)", f"US ${total_premium:,.0f}")
    col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
    col3.metric("Total Coverage", f"US ${total_coverage:,.0f}")
    col4.metric("Total Claims", f"US ${total_claims:,.0f}")

    # Custom CSS for alignment
    st.markdown(
    """ 
    <style>
    div[data-testid="metric-container"] {
        text-align: center !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stMetricLabel"] {
        text-align: center !important;
        font-size: 18px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: bold !important;
        color: #305D26 !important;
    }
    </style>
    """,
    
    unsafe_allow_html=True
)

    # 🔍 Debugging Sidebar: Check Totals Before & After Filtering
    st.sidebar.write(f"Total Unfiltered Premium: US ${df_selection['Premium'].sum():,.0f}")
    st.sidebar.write(f"Total Premium (from Payers): US ${total_premium:,.0f}")

    st.dataframe(df_premium_financing)

    # Display Filtered Data Table with Export Option
    if not df_selection.empty:
        st.write(f"Showing {len(df_selection)} records.")
       
        csv = df_selection.to_csv(index=False).encode('utf-8')
        st.download_button("Download Data as CSV", csv, "filtered_data.csv", "text/csv")
