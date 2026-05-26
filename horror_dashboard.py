import streamlit as st
import pandas as pd
import requests
import os
import random
from thefuzz import process, fuzz

st.set_page_config(page_title="Horror / SciFi / Thriller Dashboard", page_icon="👻", layout="centered")
st.title("👻 Horror / SciFi / Thriller Dashboard")

# ====================== NIGHT MODE CSS ======================
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

night_mode = st.sidebar.checkbox("🌙 Night Mode", value=st.session_state.night_mode, key="night_toggle")

if night_mode != st.session_state.night_mode:
    st.session_state.night_mode = night_mode
    st.rerun()

if st.session_state.night_mode:
    st.markdown("""
    <style>
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        .stSidebar {
            background-color: #161b22;
        }
        .stButton button {
            background-color: #21262d;
            color: #fafafa;
            border: 1px solid #30363d;
        }
        .stButton button:hover {
            background-color: #30363d;
            border-color: #58a6ff;
        }
        .stTextInput input, .stNumberInput input {
            background-color: #21262d;
            color: #fafafa;
            border: 1px solid #30363d;
        }
        .stSelectbox div, .stMultiSelect div {
            background-color: #21262d;
            color: #fafafa;
        }
        .stMarkdown, .stText, .stCaption {
            color: #c9d1d9;
        }
        .stMetric {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px;
        }
        hr {
            border-color: #30363d;
        }
    </style>
    """, unsafe_allow_html=True)

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

# ====================== LOAD MOVIES ======================
@st.cache_data(ttl=3600)
def load_movies():
    genres = {27: "Horror", 878: "SciFi", 53: "Thriller"}
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

# ====================== PERSISTENT LISTS ======================
WATCHED_FILE = "watched_list.csv"
TO_WATCH_FILE = "to_watch_list.csv"
DISLIKED_FILE = "disliked_list.csv"

def load_list(file, columns):
    if os.path.exists(file):
        df = pd.read_csv(file)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=columns)

def save_list(df, file):
    df.to_csv(file, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])

if 'to_watch' not in st.session_state:
    st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])

if 'disliked' not in st.session_state:
    st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])

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
        for idx, row in user_df.iterrows():
            title = str(row['title']).strip()
            best = search_movie_on_tmdb(title)
            if best is not None:
                matched.append({
                    'title': best['title'],
                    'year': best.get('year'),
                    'rating': row.get('rating'),
                    'matched_id': best.get('id', 999999),
                    'genre': best.get('genre', 'Mixed'),
                    'poster_path': best.get('poster_path')
                })
            else:
                skipped.append(title)
        
        if matched:
            new_df = pd.DataFrame(matched)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_list(st.session_state.watched, WATCHED_FILE)
            st.sidebar.success(f"✅ Imported {len(matched)} movies!")
            if skipped:
                st.sidebar.warning(f"Skipped {len(skipped)} movies")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# ====================== STATS ======================
st.subheader("📊 Your Stats")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Movies Watched", len(st.session_state.watched))
col2.metric("To Watch", len(st.session_state.to_watch))
col3.metric("Disliked", len(st.session_state.disliked))

if len(st.session_state.watched) > 0:
    avg_rating = st.session_state.watched['rating'].mean()
    col4.metric("Avg Rating", f"{avg_rating:.1f}" if pd.notna(avg_rating) else "N/A")

st.divider()

# ====================== SIDEBAR - MANUAL ADD ======================
st.sidebar.subheader("➕ Add Manually")

manual = st.sidebar.text_input("Type movie title (free text)")
manual_year = st.sidebar.number_input("Year (optional)", min_value=1900, max_value=2030, value=2025, step=1)
if st.sidebar.button("Add Free Text", width='stretch') and manual:
    new_entry = pd.DataFrame([{
        'title': manual,
        'year': manual_year,
        'rating': None,
        'matched_id': 999999,
        'genre': 'Mixed',
        'poster_path': None
    }])
    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
    save_list(st.session_state.watched, WATCHED_FILE)
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
            if st.sidebar.button(f"[{row['genre']}] {match_title} ({row['year']})", key=f"suggest_{match_title}"):
                new_entry = pd.DataFrame([{
                    'title': row['title'],
                    'year': row['year'],
                    'rating': None,
                    'matched_id': row['id'],
                    'genre': row['genre'],
                    'poster_path': row['poster_path']
                }])
                st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                save_list(st.session_state.watched, WATCHED_FILE)
                st.sidebar.success(f"✅ Added: {match_title}")
                st.rerun()

# Disliked movies
if len(st.session_state.disliked) > 0:
    st.sidebar.subheader("👎 Disliked Movies")
    for i, row in st.session_state.disliked.reset_index(drop=True).iterrows():
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.sidebar.caption(f"{row['title']} ({row['year']})")
        with col2:
            if st.sidebar.button("↩️", key=f"undo_{i}"):
                st.session_state.disliked = st.session_state.disliked.drop(i)
                save_list(st.session_state.disliked, DISLIKED_FILE)
                st.rerun()

# ====================== TABS ======================
tab1, tab2, tab3, tab4 = st.tabs(["📋 Watched", "🎯 Recommendations", "🔍 Search", "📝 To Watch"])

with tab1:
    st.header("Your Watched Movies")
    
    col1, col2 = st.columns([3, 2])
    with col1:
        search_term = st.text_input("🔍 Search watched movies", key="watched_search")
    with col2:
        sort_option = st.selectbox("Sort by", ["Recently Added", "Year (Newest)", "Year (Oldest)", "Rating (High to Low)", "Title A-Z"], key="watched_sort")

    filtered_watched = st.session_state.watched.copy()
    
    if search_term:
        filtered_watched = filtered_watched[filtered_watched['title'].str.contains(search_term, case=False, na=False)]
    
    if sort_option == "Year (Newest)":
        filtered_watched = filtered_watched.sort_values('year', ascending=False)
    elif sort_option == "Year (Oldest)":
        filtered_watched = filtered_watched.sort_values('year', ascending=True)
    elif sort_option == "Rating (High to Low)":
        filtered_watched = filtered_watched.sort_values('rating', ascending=False)
    elif sort_option == "Title A-Z":
        filtered_watched = filtered_watched.sort_values('title', ascending=True)

    if len(filtered_watched) > 0:
        for i, row in filtered_watched.reset_index(drop=True).iterrows():
            with st.container():
                col1, col2, col3 = st.columns([1, 5, 1])
                
                with col1:
                    if pd.notna(row.get('poster_path')) and row['poster_path'] != 'None':
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=70)
                    else:
                        st.caption("🎬")
                
                with col2:
                    genre_tag = f"[{row.get('genre', 'Mixed')}] " if 'genre' in row else ""
                    rating_text = f" • ⭐ {row['rating']}" if pd.notna(row.get('rating')) else ""
                    st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'}){rating_text}")
                    if pd.notna(row.get('overview')):
                        st.caption(str(row['overview'])[:100] + "..." if len(str(row['overview'])) > 100 else row['overview'])
                
                with col3:
                    if st.button("🗑️", key=f"del_{i}"):
                        orig_idx = st.session_state.watched[st.session_state.watched['title'] == row['title']].index[0]
                        st.session_state.watched = st.session_state.watched.drop(orig_idx)
                        save_list(st.session_state.watched, WATCHED_FILE)
                        st.rerun()
                st.divider()
        
        col1, col2 = st.columns(2)
        col1.metric("Showing", len(filtered_watched))
        if st.button("Clear All Watched", width='stretch'):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
            save_list(st.session_state.watched, WATCHED_FILE)
            st.rerun()
    else:
        st.info("No movies match your search.")

with tab2:
    st.header("🎯 Recommendations For You")
    
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        watched_titles = st.session_state.watched['title'].tolist()
        disliked_titles = st.session_state.disliked['title'].tolist() if len(st.session_state.disliked) > 0 else []
        recs = movies_df[~movies_df['title'].isin(watched_titles + disliked_titles)].copy()
        
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
        
        genre_options = ["Horror", "SciFi", "Thriller"]
        selected_genres = st.multiselect("Filter by genre", genre_options, default=genre_options)
        if selected_genres:
            recs = recs[recs['genre'].isin(selected_genres)]
        
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
                col1, col2 = st.columns([1, 5])
                
                with col1:
                    if pd.notna(row.get('poster_path')):
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=90)
                    else:
                        st.caption("🎬")
                
                with col2:
                    genre_tag = f"[{row.get('genre', 'Mixed')}] "
                    st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    st.caption(f"TMDB: {row.get('vote_average', 'N/A'):.1f}")
                    st.write(str(row['overview'])[:160] + "..." if len(str(row['overview'])) > 160 else row['overview'])
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✅ Watched", key=f"w_{idx}", width='stretch'):
                            new_entry = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'rating': None,
                                'matched_id': row.get('id', 999999),
                                'genre': row.get('genre', 'Mixed'),
                                'poster_path': row.get('poster_path')
                            }])
                            st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.watched, WATCHED_FILE)
                            st.toast(f"Added {row['title']}!", icon="⭐")
                            st.rerun()
                    with col_b:
                        if st.button("👎 Not interested", key=f"dislike_{idx}", width='stretch'):
                            new_dislike = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'matched_id': row.get('id', 999999),
                                'genre': row.get('genre', 'Mixed')
                            }])
                            st.session_state.disliked = pd.concat([st.session_state.disliked, new_dislike]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.disliked, DISLIKED_FILE)
                            st.toast(f"Got it — won't show again", icon="👎")
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
                with st.container():
                    col1, col2 = st.columns([1, 5])
                    with col1:
                        if pd.notna(row.get('poster_path')):
                            st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=90)
                        else:
                            st.caption("🎬")
                    with col2:
                        st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                        st.caption(f"TMDB: {row.get('vote_average', 'N/A')}")
                        st.write(str(row['overview'])[:180] + "..." if len(str(row['overview'])) > 180 else row['overview'])
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if not seen:
                                if st.button("✅ Watched", key=f"search_w_{i}", width='stretch'):
                                    new_entry = pd.DataFrame([{
                                        'title': row['title'],
                                        'year': row['year'],
                                        'rating': None,
                                        'matched_id': row['id'],
                                        'genre': 'Mixed',
                                        'poster_path': row['poster_path']
                                    }])
                                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                                    save_list(st.session_state.watched, WATCHED_FILE)
                                    st.toast(f"Added {row['title']}!", icon="⭐")
                                    st.rerun()
                        with col_b:
                            if st.button("➕ To Watch", key=f"search_tw_{i}", width='stretch'):
                                new_to_watch = pd.DataFrame([{
                                    'title': row['title'],
                                    'year': row['year'],
                                    'matched_id': row['id'],
                                    'genre': 'Mixed',
                                    'poster_path': row['poster_path']
                                }])
                                st.session_state.to_watch = pd.concat([st.session_state.to_watch, new_to_watch]).drop_duplicates(subset=['title'])
                                save_list(st.session_state.to_watch, TO_WATCH_FILE)
                                st.toast(f"Added {row['title']} to To Watch!", icon="📝")
                                st.rerun()
                st.divider()

with tab4:
    st.header("📝 To Watch List")
    
    if len(st.session_state.to_watch) > 0:
        for i, row in st.session_state.to_watch.reset_index(drop=True).iterrows():
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 2])
                
                with col1:
                    if pd.notna(row.get('poster_path')):
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=70)
                    else:
                        st.caption("🎬")
                
                with col2:
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                
                with col3:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✅ Watched", key=f"tw_w_{i}", width='stretch'):
                            new_entry = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'rating': None,
                                'matched_id': row.get('matched_id', 999999),
                                'genre': row.get('genre', 'Mixed'),
                                'poster_path': row.get('poster_path')
                            }])
                            st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.watched, WATCHED_FILE)
                            
                            st.session_state.to_watch = st.session_state.to_watch.drop(i)
                            save_list(st.session_state.to_watch, TO_WATCH_FILE)
                            st.rerun()
                    with col_b:
                        if st.button("🗑️", key=f"tw_del_{i}", width='stretch'):
                            st.session_state.to_watch = st.session_state.to_watch.drop(i)
                            save_list(st.session_state.to_watch, TO_WATCH_FILE)
                            st.rerun()
                st.divider()
    else:
        st.info("Your To Watch list is empty. Add movies from Recommendations!")

st.sidebar.caption("Night Mode + full feature set")
