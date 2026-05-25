import streamlit as st
import pandas as pd
import requests
import os
import random
from thefuzz import process, fuzz

st.set_page_config(page_title="Horror / SciFi / Thriller Dashboard", page_icon="👻", layout="centered")
st.title("👻 Horror / SciFi / Thriller Dashboard")

# ====================== TMDB API KEY ======================
KEY_FILE = "tmdb_key.txt"

if not os.path.exists(KEY_FILE):
    st.session_state.tmdb_key = ""
else:
    with open(KEY_FILE, "r") as f:
        st.session_state.tmdb_key = f.read().strip()

if not st.session_state.tmdb_key:
    st.sidebar.subheader("🔑 TMDB API Key Required")
    key_input = st.sidebar.text_input("Paste your Read Access Token", type="password")
    if st.sidebar.button("Save Key", width='stretch'):
        if key_input.strip().startswith("eyJ"):
            st.session_state.tmdb_key = key_input.strip()
            with open(KEY_FILE, "w") as f:
                f.write(st.session_state.tmdb_key)
            st.sidebar.success("✅ Key saved permanently!")
            st.rerun()
        else:
            st.sidebar.error("Invalid key")
    st.stop()

TMDB_TOKEN = st.session_state.tmdb_key

def tmdb_request(endpoint, params=None):
    url = f"https://api.themoviedb.org/3{endpoint}"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.status_code == 200 else None

# ====================== LOAD HORROR + SCIFI + THRILLER MOVIES ======================
@st.cache_data(ttl=3600)
def load_movies():
    genres = {
        27: "Horror",
        878: "SciFi",
        53: "Thriller"
    }
    all_movies = []
    
    for genre_id, genre_name in genres.items():
        for page in range(1, 4):
            data = tmdb_request("/discover/movie", {
                "with_genres": str(genre_id),
                "sort_by": "popularity.desc",
                "vote_count.gte": 50,
                "page": page
            })
            if data and 'results' in data:
                for m in data['results']:
                    all_movies.append({
                        'title': m.get('title') or m.get('original_title'),
                        'year': m.get('release_date', '')[:4] if m.get('release_date') else None,
                        'overview': m.get('overview', ''),
                        'vote_average': m.get('vote_average'),
                        'poster_path': m.get('poster_path'),
                        'id': m.get('id'),
                        'genre': genre_name
                    })
    
    df = pd.DataFrame(all_movies)
    df = df.dropna(subset=['title'])
    df = df.drop_duplicates(subset=['title'])
    return df

movies_df = load_movies()

# ====================== PERSISTENT WATCHED + DISLIKED LISTS ======================
WATCHED_FILE = "watched_list.csv"
DISLIKED_FILE = "disliked_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id', 'genre'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

def load_disliked_list():
    if os.path.exists(DISLIKED_FILE):
        return pd.read_csv(DISLIKED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'matched_id', 'genre'])

def save_disliked_list(df):
    df.to_csv(DISLIKED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

if 'disliked' not in st.session_state:
    st.session_state.disliked = load_disliked_list()

# ====================== TMDB SEARCH ======================
def search_movie_on_tmdb(title):
    data = tmdb_request("/search/movie", {"query": title, "page": 1})
    if data and 'results' in data and data['results']:
        best = data['results'][0]
        return {
            'title': best.get('title') or best.get('original_title'),
            'year': best.get('release_date', '')[:4] if best.get('release_date') else None,
            'overview': best.get('overview', ''),
            'vote_average': best.get('vote_average'),
            'poster_path': best.get('poster_path'),
            'id': best.get('id'),
            'genre': 'Mixed'
        }
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
        skipped = []
        progress = st.sidebar.progress(0)
        total = len(user_df)
        
        for idx, row in user_df.iterrows():
            title = str(row['title']).strip()
            best = search_movie_on_tmdb(title)
            if best is not None:
                matched.append({
                    'title': best['title'],
                    'year': best.get('year'),
                    'rating': row.get('rating'),
                    'matched_id': best.get('id', 999999),
                    'genre': best.get('genre', 'Mixed')
                })
            else:
                skipped.append(title)
            progress.progress((idx + 1) / total)
        
        if matched:
            new_df = pd.DataFrame(matched)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_watched_list(st.session_state.watched)
            st.sidebar.success(f"✅ Imported {len(matched)} movies!")
            if skipped:
                st.sidebar.warning(f"Skipped {len(skipped)} movies. First few: {skipped[:10]}")
            st.rerun()
        else:
            st.sidebar.warning("No movies matched.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# ====================== MANUAL ADD + FUZZY SEARCH ======================
st.sidebar.subheader("➕ Add Manually")

manual = st.sidebar.text_input("Type movie title (free text)")
manual_year = st.sidebar.number_input("Year (optional)", min_value=1900, max_value=2030, value=2025, step=1)
if st.sidebar.button("Add Free Text", width='stretch') and manual:
    new_entry = pd.DataFrame([{
        'title': manual,
        'year': manual_year,
        'rating': None,
        'matched_id': 999999,
        'genre': 'Mixed'
    }])
    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
    save_watched_list(st.session_state.watched)
    st.sidebar.success(f"✅ Added: {manual}")
    st.rerun()

st.sidebar.markdown("**Or use fuzzy search:**")
search_query = st.sidebar.text_input("Start typing a movie name...", key="fuzzy_search")

if search_query and len(search_query) >= 2:
    titles = movies_df['title'].tolist()
    matches = process.extract(search_query, titles, scorer=fuzz.token_sort_ratio, limit=5)
    
    st.sidebar.write("**Suggestions:**")
    for match_title, score in matches:
        if score >= 50:
            row = movies_df[movies_df['title'] == match_title].iloc[0]
            genre_tag = f"[{row['genre']}] "
            if st.sidebar.button(f"{genre_tag}{match_title} ({row['year']})", key=f"suggest_{match_title}"):
                new_entry = pd.DataFrame([{
                    'title': row['title'],
                    'year': row['year'],
                    'rating': None,
                    'matched_id': row['id'],
                    'genre': row['genre']
                }])
                st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                save_watched_list(st.session_state.watched)
                st.sidebar.success(f"✅ Added: {match_title}")
                st.rerun()

# Disliked movies section in sidebar
if len(st.session_state.disliked) > 0:
    st.sidebar.subheader("👎 Disliked Movies")
    for i, row in st.session_state.disliked.reset_index(drop=True).iterrows():
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.sidebar.caption(f"{row['title']} ({row['year']})")
        with col2:
            if st.sidebar.button("↩️", key=f"undo_{i}"):
                # Move back to watched or just remove from disliked
                st.session_state.disliked = st.session_state.disliked.drop(i)
                save_disliked_list(st.session_state.disliked)
                st.rerun()

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search"])

with tab1:
    st.header("Your Watched Movies")
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
                genre_tag = f"[{row.get('genre', 'Mixed')}] " if 'genre' in row else ""
                st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
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
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id', 'genre'])
            save_watched_list(st.session_state.watched)
            st.rerun()
    else:
        st.info("No movies yet. Import from Letterboxd or add manually.")

with tab2:
    st.header("🎯 Recommendations For You")
    
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        watched_titles = st.session_state.watched['title'].tolist()
        disliked_titles = st.session_state.disliked['title'].tolist() if len(st.session_state.disliked) > 0 else []
        
        # Filter out watched + disliked
        recs = movies_df[~movies_df['title'].isin(watched_titles + disliked_titles)].copy()
        
        # Boost with similar movies
        if len(st.session_state.watched) > 0:
            random_watched = st.session_state.watched.sample(1).iloc[0]
            similar_data = tmdb_request(f"/movie/{random_watched['matched_id']}/similar", {"page": 1})
            if similar_data and 'results' in similar_data:
                similar_movies = []
                for m in similar_data['results'][:10]:
                    similar_movies.append({
                        'title': m.get('title') or m.get('original_title'),
                        'year': m.get('release_date', '')[:4] if m.get('release_date') else None,
                        'overview': m.get('overview', ''),
                        'vote_average': m.get('vote_average'),
                        'poster_path': m.get('poster_path'),
                        'id': m.get('id'),
                        'genre': 'Mixed'
                    })
                similar_df = pd.DataFrame(similar_movies)
                recs = pd.concat([recs, similar_df]).drop_duplicates(subset=['title'])
        
        # Genre filter
        genre_options = ["Horror", "SciFi", "Thriller"]
        selected_genres = st.multiselect("Filter by genre", genre_options, default=genre_options)
        
        if selected_genres:
            recs = recs[recs['genre'].isin(selected_genres)]
        
        # Vibe filter
        vibe_options = ["Found Footage", "Supernatural", "Slasher", "Psychological", "Alien / Space", "Dystopian", "Serial Killer", "Mind-Bending"]
        selected_vibes = st.multiselect("Filter by vibe", vibe_options, default=[])
        
        if selected_vibes:
            keyword_map = {
                "Found Footage": ["found footage", "handheld"],
                "Supernatural": ["supernatural", "ghost", "haunted", "demon"],
                "Slasher": ["slasher", "killer", "blood"],
                "Psychological": ["psychological", "slow burn", "mind"],
                "Alien / Space": ["alien", "space", "planet", "sci-fi"],
                "Dystopian": ["dystopian", "future", "society"],
                "Serial Killer": ["serial", "killer", "murder"],
                "Mind-Bending": ["mind-bending", "twist", "reality"]
            }
            mask = pd.Series(False, index=recs.index)
            for vibe in selected_vibes:
                for kw in keyword_map.get(vibe, []):
                    mask |= recs['overview'].str.contains(kw, case=False, na=False)
            recs = recs[mask]
        
        recs = recs.head(15)
        
        for idx, row in recs.iterrows():
            with st.container():
                if 'poster_path' in row and pd.notna(row.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=140)
                genre_tag = f"[{row.get('genre', 'Mixed')}] "
                st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                st.caption(f"TMDB: {row.get('vote_average', 'N/A'):.1f}")
                st.write(str(row['overview'])[:180] + "..." if len(str(row['overview'])) > 180 else row['overview'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Mark as Watched", key=f"w_{idx}", width='stretch'):
                        new_entry = pd.DataFrame([{
                            'title': row['title'],
                            'year': row['year'],
                            'rating': None,
                            'matched_id': row.get('id', 999999),
                            'genre': row.get('genre', 'Mixed')
                        }])
                        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                        save_watched_list(st.session_state.watched)
                        st.toast(f"Added {row['title']}!", icon="⭐")
                        st.rerun()
                with col2:
                    if st.button("👎 Not interested", key=f"dislike_{idx}", width='stretch'):
                        new_dislike = pd.DataFrame([{
                            'title': row['title'],
                            'year': row['year'],
                            'matched_id': row.get('id', 999999),
                            'genre': row.get('genre', 'Mixed')
                        }])
                        st.session_state.disliked = pd.concat([st.session_state.disliked, new_dislike]).drop_duplicates(subset=['title'])
                        save_disliked_list(st.session_state.disliked)
                        st.toast(f"Got it — won't show {row['title']} again", icon="👎")
                        st.rerun()
                st.divider()

with tab3:
    st.header("🔍 Search Movies")
    q = st.text_input("Type any movie name (fuzzy search)")
    if q:
        results = tmdb_request("/search/movie", {"query": q, "page": 1})
        if results and 'results' in results:
            for i, movie in enumerate(results['results'][:12]):
                row = {
                    'title': movie.get('title') or movie.get('original_title'),
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else None,
                    'overview': movie.get('overview', ''),
                    'vote_average': movie.get('vote_average'),
                    'poster_path': movie.get('poster_path'),
                    'id': movie.get('id'),
                    'genre': 'Mixed'
                }
                seen = row['title'] in st.session_state.watched['title'].values
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    st.caption(f"TMDB Rating: {row.get('vote_average', 'N/A')}")
                    st.write(str(row['overview'])[:220] + "..." if len(str(row['overview'])) > 220 else row['overview'])
                with col2:
                    if not seen:
                        if st.button("Add to Watched", key=f"search_add_{i}"):
                            new_entry = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'rating': None,
                                'matched_id': row['id'],
                                'genre': 'Mixed'
                            }])
                            st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                            save_watched_list(st.session_state.watched)
                            st.toast(f"Added {row['title']}!", icon="⭐")
                            st.rerun()

st.sidebar.caption("Horror + SciFi + Thriller • Downvote feature added")
