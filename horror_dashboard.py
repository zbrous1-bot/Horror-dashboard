import streamlit as st
import pandas as pd
import requests
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")
st.title("👻 Horror Dashboard")

# ====================== TMDB API SETUP ======================
if 'tmdb_key' not in st.session_state:
    st.session_state.tmdb_key = ""

if not st.session_state.tmdb_key:
    st.sidebar.subheader("🔑 Enter your TMDB API Key")
    key_input = st.sidebar.text_input("Paste your Read Access Token here", type="password")
    if st.sidebar.button("Save Key", width='stretch'):
        if key_input.strip().startswith("eyJ"):
            st.session_state.tmdb_key = key_input.strip()
            st.sidebar.success("✅ Key saved!")
            st.rerun()
        else:
            st.sidebar.error("That doesn't look like a valid TMDB key.")
    st.stop()  # Stop until key is entered

TMDB_TOKEN = st.session_state.tmdb_key

def tmdb_request(endpoint, params=None):
    url = f"https://api.themoviedb.org/3{endpoint}"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"TMDB API error: {response.status_code}")
        return None

# ====================== LOAD HORROR MOVIES (real-time) ======================
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_horror_data():
    data = tmdb_request("/discover/movie", {
        "with_genres": "27",      # 27 = Horror
        "sort_by": "popularity.desc",
        "page": 1,
        "vote_count.gte": 100
    })
    if not data or 'results' not in data:
        st.error("Could not load movies from TMDB.")
        return pd.DataFrame()
    
    movies = []
    for m in data['results']:
        movies.append({
            'title': m.get('title') or m.get('original_title'),
            'year': m.get('release_date', '')[:4] if m.get('release_date') else None,
            'overview': m.get('overview', ''),
            'vote_average': m.get('vote_average'),
            'poster_path': m.get('poster_path'),
            'id': m.get('id')
        })
    df = pd.DataFrame(movies)
    df = df.dropna(subset=['title'])
    return df

horror_df = load_horror_data()

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

# ====================== SIDEBAR ======================
st.sidebar.header("📥 Import from Letterboxd")
# ... (your existing import code remains the same)

st.sidebar.subheader("🎬 Force Add Any Movie")
force_title = st.sidebar.text_input("Movie title")
force_year = st.sidebar.number_input("Year", min_value=1900, max_value=2030, value=2024, step=1)
if st.sidebar.button("Force Add", width='stretch') and force_title:
    new_entry = pd.DataFrame([{'title': force_title, 'year': force_year, 'rating': None, 'matched_id': 999999}])
    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
    save_watched_list(st.session_state.watched)
    st.sidebar.success(f"Added {force_title}")
    st.rerun()

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search"])

with tab1:
    # Your existing Watched tab with delete buttons and remove duplicates
    st.header("Your Watched Horror Movies")
    if len(st.session_state.watched) > 0:
        if st.button("🧹 Remove Duplicates", width='stretch'):
            before = len(st.session_state.watched)
            st.session_state.watched = st.session_state.watched.drop_duplicates(subset=['title'], keep='first')
            save_watched_list(st.session_state.watched)
            st.success(f"Removed {before - len(st.session_state.watched)} duplicate(s)")
            st.rerun()
        # Individual delete buttons...
        # (same as previous version)

with tab2:
    st.header("🎯 Recommendations For You")
    # Subgenre filters + real-time TMDB posters
    # (same as before, but now uses fresh data)

with tab3:
    st.header("🔍 Search Movies")
    # Fuzzy search with bio (same as before)

st.sidebar.caption("Real-time TMDB • Updated May 2026")
