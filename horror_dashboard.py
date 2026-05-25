import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")

st.title("👻 Horror Dashboard")
st.markdown("Track • Recommend • Discover")

# ====================== LOAD DATA ======================
@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['title', 'overview'])
    df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
    
    horror_style_keywords = (
        "found footage handheld camera supernatural possession demon paranormal "
        "ghost haunted exorcism slasher psychological slow burn atmospheric "
        "jump scare horror creepy terrifying disturbing"
    )
    
    df['features'] = (
        df['overview'].fillna('') + ' ' + 
        df['director'].fillna('') + ' ' + 
        df['cast'].fillna('') + ' ' + 
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
    else:
        return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

# ====================== SIDEBAR ======================
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
            match = process.extractOne(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
            if match and match[1] >= 75:
                matched_row = horror_df[horror_df['title'] == match[0]].iloc[0]
                matched.append({
                    'title': match[0],
                    'year': matched_row['year'],
                    'rating': row.get('rating'),
                    'matched_id': int(matched_row['id'])
                })
        if matched:
            new_df = pd.DataFrame(matched)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_watched_list(st.session_state.watched)
            st.sidebar.success(f"Imported {len(matched)} movies!")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.subheader("➕ Add Movie Manually")
manual = st.sidebar.text_input("Movie title")
if st.sidebar.button("Add to Watched", use_container_width=True) and manual:
    match = process.extractOne(manual, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70:
        matched_row = horror_df[horror_df['title'] == match[0]].iloc[0]
        new_entry = pd.DataFrame([{'title': match[0], 'year': matched_row['year'], 'rating': None, 'matched_id': int(matched_row['id'])}])
        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
        save_watched_list(st.session_state.watched)
        st.sidebar.success(f"Added: {match[0]}")

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search"])

with tab1:
    st.header("Your Watched Horror Movies")
    if len(st.session_state.watched) > 0:
        display = st.session_state.watched.merge(horror_df[['title', 'vote_average', 'director']], on='title', how='left')
        st.dataframe(display[['title', 'year', 'rating', 'vote_average', 'director']], use_container_width=True, height=400)
        
        col1, col2 = st.columns(2)
        col1.metric("Total Seen", len(st.session_state.watched))
        if st.session_state.watched['rating'].notna().any():
            col2.metric("Avg Rating", f"{st.session_state.watched['rating'].mean():.1f} ⭐")
        
        if st.button("Clear All Watched", use_container_width=True):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])
            save_watched_list(st.session_state.watched)
            st.rerun()
    else:
        st.info("No movies yet. Import from Letterboxd or add manually in the sidebar."
