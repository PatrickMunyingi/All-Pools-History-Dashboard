import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import scipy
import matplotlib.pyplot as plt
st.set_page_config(page_title='All Pools History Dashboard',layout='wide',initial_sidebar_state='expanded')


df=pd.read_excel('C:/Users/PatrickMunyingi/all pools.xlsx')
df.fillna(0,inplace=True,axis=1)

#Here we want to create our dashboard filters.
# The filters here will allow us to select the data that we want to vizualise.

st.sidebar.header("Please Filter Here:")
pool = st.sidebar.multiselect("Select the Pool:", options=df["Pool"].unique(), default=df["Pool"].unique())
policy_type = st.sidebar.multiselect("Select the Policy Type:", options=df["Policy Type"].unique(), default=df["Policy Type"].unique())
country=st.sidebar.multiselect("Select the prefered country",options=df["Country"].unique(),default=df['Country'].unique())

df_selection = df.query('`Policy Type` == @policy_type and Pool == @pool and `Country`==@country')


##--MAINPAGE--
st.title("ALL POOLS HISTORY DASHBOARD")
st.markdown('##')
option=st.selectbox("What would you like to view?",('Premium and country basic Infomation','Premium financing and Tracker','Claim settlement history'),index=None,placeholder="Select What you would like to see")

if option=="Premium and country basic Infomation":

        ## -----TOP KPI's-----
    total_premium=int(df_selection['Premium'].sum())
    total_attachment=int(df_selection['Attachment'].sum())
    total_exhaustion=int(df_selection['Exhaustion'].sum())
    total_coverage=int(df_selection['Coverage'].sum())

    left_column,middle_column,right_column,final_column=st.columns(4)# Defining the placement of the data cards with the attachment, exhaustion,coverage,etc
    with left_column:
        st.subheader("Total Premium")
        st.subheader(f"US ${total_premium:,}")
            
            
            
            
    with middle_column:
        st.subheader("Attachment Point:")
        st.subheader(f"US ${total_attachment:,}")





    with right_column:
        st.subheader("'Total exhaustion")
        st.subheader(f"US ${total_exhaustion:,}")
            



    with final_column:
        st.subheader("'Total Coverage")
        st.subheader(f"US ${total_coverage:,}")





    coluumn_a,column_b,column_c=st.columns(3)
    with coluumn_a:
            ## Yearly progression--
        plot1=plt.figure(figsize=(7,7))
        plot1=px.line(df_selection.groupby('Policy Years')['Premium'].sum(),markers=True,title='Yearly Pool progression of premiums',template='plotly_white')
        st.plotly_chart(plot1)
    with column_b:
            ## Country count
        plot2=plt.figure(figsize=(5,6))
        plot2=px.bar(df_selection.groupby('Country')['Country'].count(),orientation='h')
        st.plotly_chart(plot2)

    with column_c:
        policy_type_counts = df_selection['Policy Type'].value_counts().reset_index()

            # Rename the columns to match Plotly Express expectations
        policy_type_counts.columns = ['Policy Type', 'Count']

            # Create the pie chart using Plotly Express
        fig=plt.figure(figsize=(5,5))
        fig = px.pie(policy_type_counts, names='Policy Type', values='Count', hole=0.6)
        st.plotly_chart(fig)
else:
    print("Select an option please")
    
    