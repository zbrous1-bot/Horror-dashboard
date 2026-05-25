import streamlit as st
import pandas as pd

st.title("🔍 Dataset Diagnostic")

df = pd.read_csv("best_horror_movies.csv")

st.write("### Your CSV has these columns:")
st.write(df.columns.tolist())

st.write("### First 5 rows:")
st.dataframe(df.head())

st.info("Copy the list of columns above and reply to me with it. I'll update the app code for you.")
