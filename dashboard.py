import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import scipy
import matplotlib.pyplot as plt
st.set_page_config(page_title='All Pools History Dashboard',layout='wide',initial_sidebar_state='expanded')



@st.cache_data
def load_data():
    return pd.read_excel('all pools.xlsx', usecols=None)  # Load only needed columns if applicable

df = load_data()

# Ensure numerical columns are properly formatted
numeric_cols = ['Premium', 'Attachment', 'Exhaustion', 'Coverage', 'Claims']
df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

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
st.title("ALL POOLS HISTORY DASHBOARD")
st.markdown('##')

option = st.selectbox("What would you like to view?", 
                      ("", "Premium and country basic Information", "Premium financing and Tracker", "Claim settlement history", "Re-Insurance Information"))

if option == "Premium and country basic Information":
    # KPI Calculations
    total_premium = df_selection['Premium'].sum()
    total_claims = df_selection['Claims'].sum()
    total_coverage = df_selection['Coverage'].sum()
    loss_ratio = (total_claims / total_premium) * 100 if total_premium > 0 else 0

 # Custom CSS for alignment
    




    # KPI Display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Premium", f"US ${total_premium:,.0f}")
    col2.metric("Loss Ratio", f"{loss_ratio:.2f}%")
    col3.metric("Total Coverage", f"US ${total_coverage:,.0f}")
    col4.metric("Total Claims", f"US ${total_claims:,.0f}")

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

    # Display Filtered Data Table
    if not df_selection.empty:
        st.write(f"Showing {len(df_selection)} records.")
        st.dataframe(df_selection)
    else:
        st.warning("No data available for the selected filters.")

else:
    st.warning("Select an option to view data.")
