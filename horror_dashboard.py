import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")
st.title("👻 Horror Dashboard")

@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['title', 'overview'])
    
    if 'release_year' in df.columns:
        df['year'] = df['release_year']
    elif 'year' not in df.columns:
        df['year'] = pd.to_datetime(df.get('release_date', pd.Series()), errors='coerce').dt.year
    
    horror_style_keywords = "found footage handheld camera supernatural possession demon paranormal ghost haunted exorcism slasher psychological slow burn atmospheric jump scare horror creepy terrifying disturbing"
    
    director_col = df.get('director', pd.Series([''] * len(df))).fillna('')
    cast_col = df.get('cast', pd.Series([''] * len(df))).fillna('')
    
    df['features'] = df['overview'].fillna('') + ' ' + director_col + ' ' + cast_col + ' ' + horror_style_keywords
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()

@st.cache_data
def compute_similarity_matrix(features):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf = vectorizer.fit_transform(features)
    return cosine_similarity(tfidf)

WATCHED_FILE = "watched_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

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

st.sidebar.header("📥 Import from Letterboxd")
uploaded = st.sidebar.file_uploader("Upload diary.csv", type="csv")

if uploaded:
    try:
        user_df = pd.read_csv(uploaded)
        if 'Name' in user_df.columns:
            user_df = user_df.rename(columns={'Name': 'title', 'Year': 'year', 'Rating': 'rating'})
        if 'title' not in user_df.columns:
            user_df = user_df.rename(columns={user_df.columns[0]: 'title'})
        if 'year' not in user_df.columns:
            user_df['year'] = None
        if 'rating' not in user_df.columns:
            user_df['rating'] = None
        matched = []
        for _, row in user_df.iterrows():
            title = str(row['title']).strip()
            year = row.get('year')
            best_row = smart_match(title, year)
            if best_row is not None:
                matched.append({'title': best_row['title'], 'year': best_row['year'], 'rating': row.get('rating'), 'matched_id': int(best_row['id'])})
        if matched:
            new_df = pd.DataFrame(matched)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_watched_list(st.session_state.watched)
            st.sidebar.success(f"Imported {len(matched)} movies!")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.subheader("➕ Add Manually")
manual = st.sidebar.text_input("Movie title")
manual_year = st.sidebar.number_input("Year (optional)", min_value=1900, max_value=2030, value=2025, step=1)
if st.sidebar.button("Add", use_container_width=True) and manual:
    best_row = smart_match(manual, manual_year)
    if best_row is not None:
        new_entry = pd.DataFrame([{'title': best_row['title'], 'year': best_row['year'], 'rating': None, 'matched_id': int(best_row['id'])}])
        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
        save_watched_list(st.session_state.watched)
        st.sidebar.success(f"Added: {best_row['title']} ({best_row['year']})")
    else:
        st.sidebar.error("Movie not found. Try different spelling or add the year.")

tab1, tab2, tab3 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search"])

with tab1:
    st.header("Your Watched Horror Movies")
    if len(st.session_state.watched) == 0:
