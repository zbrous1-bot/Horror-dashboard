import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")
st.title("👻 Horror Dashboard")

# ====================== LOAD DATA ======================
@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['title', 'overview'])
    
    # Handle year column
    if 'release_year' in df.columns:
        df['year'] = df['release_year']
    elif 'year' not in df.columns:
        df['year'] = pd.to_datetime(df.get('release_date', pd.Series()), errors='coerce').dt.year
    
    horror_style_keywords = "found footage handheld camera supernatural possession demon paranormal ghost haunted exorcism slasher psychological slow burn atmospheric jump scare horror creepy terrifying disturbing"
    
    # Safely get director and cast (they might not exist)
    director_col = df.get('director', pd.Series([''] * len(df))).fillna('')
    cast_col = df.get('cast', pd.Series([''] * len(df))).fillna('')
    
    df['features'] = (
        df['overview'].fillna('') + ' ' + 
        director_col + ' ' + 
        cast_col + ' ' + 
        horror_style_keywords
    )
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()

@st.cache_data
def compute_similarity_matrix(features):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf = vectorizer.fit_transform(features)
    return cosine_similarity(tfidf)

# ====================== PERSISTENT WATCHED LIST ======================
WATCHED_FILE = "watched_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

# ====================== SMART MATCHING WITH YEAR ======================
def smart_match(title, year=None):
    matches = process.extract(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=10)
    best_match = None
    best_score = 0
    
    for match_title, score in matches:
        if score < 65:
            continue
        matched_row = horror_df[horror_df['title'] == match_title].iloc[0]
        movie_year = matched_row.get('year')
        
        year_bonus = 0
        if year and pd.notna(movie_year):
            year_diff = abs(int(year) - int(movie_year))
            if year_diff == 0:
                year_bonus = 25
            elif year_diff <= 2:
                year_bonus = 15
            elif year_diff <= 5:
                year_bonus = 8
        
        final_score = score + year_bonus
        if final_score > best_score:
            best_score = final_score
            best_match = matched_row
    
    if best_match is not None and best_score >= 75:
        return best_match
    return None

# ====================== SIDEBAR ======================
st.sidebar.header("📥 Import from Letterboxd")
uploaded = st.sidebar.file_uploader("Upload diary.csv", type="csv")

if uploaded:
    try:
        user_df = pd.read_csv(uploaded)
        if 'Name' in user_df.columns:
            user_df = user_df.rename(columns={'Name': 'title', 'Year': 'year', 'Rating': 'rating'})
        if 'title' not in user_df.columns:
            user_df =
