import streamlit as st
import pandas as pd
import requests
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")
st.title("👻 Horror Dashboard")

# ====================== TMDB API KEY (saved to file for permanence) ======================
KEY_FILE = "tmdb_key.txt"

if not os.path.exists(KEY_FILE):
    st.session_state.tmdb_key = ""
else:
    with open(KEY_FILE, "r") as f:
        st.session_state.tmdb_key = f.read().strip()

if not st.session_state.tmdb_key:
    st.sidebar.subheader("🔑 TMDB API Key Required")
    key_input = st.sidebar.text_input("Paste your Read Access Token (starts with eyJ...)", type="password")
    if st.sidebar.button("Save Key", width='stretch'):
        if key_input.strip().startswith("eyJ"):
            st.session_state.tmdb_key = key_input.strip()
            with open(KEY_FILE, "w") as f:
                f.write(st.session_state.tmdb_key)
            st.sidebar.success("✅ Key saved permanently!")
            st.rerun()
        else:
            st.sidebar.error("Invalid key. Must start with 'eyJ'")
    st.stop()

TMDB_TOKEN = st.session_state.tmdb_key

def tmdb_request(endpoint, params=None):
    url = f"https://api.themoviedb.org/3{endpoint}"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.status_code == 200 else None

# ====================== LOAD HORROR MOVIES ======================
@st.cache_data(ttl=3600)
def load_horror_data():
    data = tmdb_request("/discover/movie", {
        "with_genres": "27",
        "sort_by": "popularity.desc",
        "vote_count.gte": 100,
        "page": 1
    })
    if not data or 'results' not in data:
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

def smart_match(title, year=None):
    matches = process.extract(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=15)
    best_match = None
    best_score = 0
    for match_title, score in matches:
        if score < 68: continue
        matched_row = horror_df[horror_df['title'] == match_title].iloc[0]
        movie_year = matched_row.get('year')
        penalty = 0
        if "alien" in title.lower() and ("3" in match_title.lower() or "iii" in match_title.lower()):
            penalty = 40
        year_bonus = 0
        if year and pd.notna(movie_year):
            year_diff = abs(int(year) - int(movie_year))
            if year_diff == 0: year_bonus = 35
            elif year_diff <= 1: year_bonus = 22
            elif year_diff <= 3: year_bonus = 12
        final_score = score - penalty + year_bonus
        if final_score > best_score:
            best_score = final_score
            best_match = matched_row
    if best_match is not None and best_score >= 78:
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
                matched.append({
                    'title': best_row['title'],
                    'year': best_row['year'],
                    'rating': row.get('rating'),
                    'matched_id': best_row.name
                })
        if matched:
            new_df = pd.DataFrame(matched)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_watched_list(st.session_state.watched)
            st.sidebar.success(f"Imported {len(matched)} movies!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.subheader("➕ Add Manually")
manual = st.sidebar.text_input("Movie title")
manual_year = st.sidebar.number_input("Year (optional)", min_value=1900, max_value=2030, value=2025, step=1)
if st.sidebar.button("Add", width='stretch') and manual:
    best_row = smart_match(manual, manual_year)
    if best_row is not None:
        new_entry = pd.DataFrame([{'title': best_row['title'], 'year': best_row['year'], 'rating': None, 'matched_id': best_row.name}])
    else:
        new_entry = pd.DataFrame([{'title': manual, 'year': manual_year, 'rating': None, 'matched_id': 999999}])
    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
    save_watched_list(st.session_state.watched)
    st.sidebar.success(f"Added: {manual}")
    st.rerun()

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search"])

with tab1:
    st.header("Your Watched Horror Movies")
    if len(st.session_state.watched) > 0:
        if st.button("🧹 Remove Duplicates", width='stretch'):
            before = len(st.session_state.watched)
            st.session_state.watched = st.session_state.watched.drop_duplicates(subset=['title'], keep='first')
            save_watched_list(st.session_state.watched)
            st.success(f"Removed {before - len(st.session_state.watched)} duplicate(s)")
            st.rerun()
        for i, row in st.session_state.watched.reset_index(drop=True).iterrows():
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
            with col2:
                if st.button("🗑️", key=f"del_{i}"):
                    orig_idx = st.session_state.watched[st.session_state.watched['title'] == row['title']].index[0]
                    st.session_state.watched = st.session_state.watched.drop(orig_idx)
                    save_watched_list(st.session_state.watched)
                    st.rerun()
        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("Total Seen", len(st.session_state.watched))
        if st.button("Clear All", width='stretch'):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])
            save_watched_list(st.session_state.watched)
            st.rerun()
    else:
        st.info("No movies yet. Import from Letterboxd or add manually.")

with tab2:
    st.header("🎯 Recommendations For You")
    subgenre_options = ["Found Footage", "Supernatural / Possession", "Slasher", "Psychological", "Paranormal / Ghost", "Demonic"]
    selected_subgenres = st.multiselect("Filter by subgenre", subgenre_options, default=[])
    
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        watched_titles = st.session_state.watched['title'].tolist()
        recs = horror_df[~horror_df['title'].isin(watched_titles)].copy()
        if selected_subgenres:
            keyword_map = {
                "Found Footage": ["found footage", "handheld"],
                "Supernatural / Possession": ["supernatural", "possession", "demon", "exorcism"],
                "Slasher": ["slasher", "killer", "blood"],
                "Psychological": ["psychological", "slow burn"],
                "Paranormal / Ghost": ["paranormal", "ghost", "haunted"],
                "Demonic": ["demonic", "devil"]
            }
            mask = pd.Series(False, index=recs.index)
            for genre in selected_subgenres:
                for kw in keyword_map.get(genre, []):
                    mask |= recs['overview'].str.contains(kw, case=False, na=False)
            recs = recs[mask]
        recs = recs.head(12)
        for idx, row in recs.iterrows():
            with st.container():
                if 'poster_path' in row and pd.notna(row.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=140)
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                st.caption(f"TMDB: {row.get('vote_average', 'N/A'):.1f}")
                st.write(str(row['overview'])[:180] + "..." if len(str(row['overview'])) > 180 else row['overview'])
                if st.button("✅ Mark as Watched", key=f"w_{idx}", width='stretch'):
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': idx}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                    save_watched_list(st.session_state.watched)
                    st.toast(f"Added {row['title']}!", icon="⭐")
                    st.rerun()
                st.divider()

with tab3:
    st.header("🔍 Search Movies")
    q = st.text_input("Type any movie name (fuzzy search)")
    if q:
        matches = process.extract(q, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=10)
        for i, (match_title, score) in enumerate(matches):
            if score < 65: continue
            row = horror_df[horror_df['title'] == match_title].iloc[0]
            seen = row['title'] in st.session_state.watched['title'].values
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                st.caption(f"Match: {score}%")
                st.write(str(row['overview'])[:220] + "..." if len(str(row['overview'])) > 220 else row['overview'])
            with col2:
                if not seen:
                    if st.button("Add to Watched", key=f"search_add_{i}"):
                        new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': row.name}])
                        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                        save_watched_list(st.session_state.watched)
                        st.toast(f"Added {row['title']}!", icon="⭐")
                        st.rerun()

st.sidebar.caption("Key now saved permanently")
