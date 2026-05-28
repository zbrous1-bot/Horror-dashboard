import streamlit as st
import pandas as pd
import requests
import os
import random
from thefuzz import process, fuzz

st.set_page_config(page_title="Brous Movie Dashboard", page_icon="🎥", layout="wide")

# ====================== NIGHT MODE ======================
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

night_mode = st.sidebar.checkbox("🌙 Night Mode", value=st.session_state.night_mode, key="night_toggle")

if night_mode != st.session_state.night_mode:
    st.session_state.night_mode = night_mode
    st.rerun()

if st.session_state.night_mode:
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stSidebar { background-color: #161b22; }
        .stButton button { background-color: #21262d; color: #fafafa; border: 1px solid #30363d; }
        .stButton button:hover { background-color: #30363d; border-color: #58a6ff; }
        .stTextInput input, .stNumberInput input { background-color: #21262d; color: #fafafa; border: 1px solid #30363d; }
        .stSelectbox div, .stMultiSelect div { background-color: #21262d; color: #fafafa; }
        .stMarkdown, .stText, .stCaption { color: #c9d1d9; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px; }
        hr { border-color: #30363d; }
        
        .stTabs [data-baseweb="tab-list"] button {
            font-size: 18px !important;
            font-weight: 600 !important;
            padding: 12px 24px !important;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] button {
            font-size: 18px !important;
            font-weight: 600 !important;
            padding: 12px 24px !important;
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

def get_movie_details(movie_id):
    return tmdb_request(f"/movie/{movie_id}", {"append_to_response": "credits,external_ids"})

# ====================== LOAD MOVIES (EXPANDED) ======================
@st.cache_data(ttl=3600)
def load_movies():
    genres = {
        27: "Horror", 
        878: "SciFi", 
        53: "Thriller",
        28: "Action",
        12: "Adventure",
        9648: "Mystery",
        14: "Fantasy",
        80: "Crime",
        18: "Drama",
        35: "Comedy"
    }
    all_movies = []
    for genre_id, genre_name in genres.items():
        for page in range(1, 5):
            data = tmdb_request("/discover/movie", {
                "with_genres": str(genre_id),
                "sort_by": "popularity.desc",
                "vote_count.gte": 30,
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
        try:
            df = pd.read_csv(file)
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            return df
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_list(df, file):
    df.to_csv(file, index=False)

# ====================== BACKUP & RESTORE ======================
st.sidebar.subheader("💾 Backup & Restore")

if st.sidebar.button("📥 Download Watched"):
    if len(st.session_state.watched) > 0:
        st.download_button("Download watched_list.csv", st.session_state.watched.to_csv(index=False), "watched_list.csv", "text/csv")
    else:
        st.sidebar.warning("Nothing to download")

if st.sidebar.button("📥 Download To Watch"):
    if len(st.session_state.to_watch) > 0:
        st.download_button("Download to_watch_list.csv", st.session_state.to_watch.to_csv(index=False), "to_watch_list.csv", "text/csv")
    else:
        st.sidebar.warning("Nothing to download")

if st.sidebar.button("📥 Download Disliked"):
    if len(st.session_state.disliked) > 0:
        st.download_button("Download disliked_list.csv", st.session_state.disliked.to_csv(index=False), "disliked_list.csv", "text/csv")
    else:
        st.sidebar.warning("Nothing to download")

# Restore
st.sidebar.subheader("📤 Restore Backup")
up_w = st.sidebar.file_uploader("Upload watched_list.csv", type="csv", key="up_w")
if up_w:
    st.session_state.watched = pd.read_csv(up_w)
    save_list(st.session_state.watched, WATCHED_FILE)
    st.sidebar.success("✅ Watched restored!")
    st.rerun()

up_tw = st.sidebar.file_uploader("Upload to_watch_list.csv", type="csv", key="up_tw")
if up_tw:
    st.session_state.to_watch = pd.read_csv(up_tw)
    save_list(st.session_state.to_watch, TO_WATCH_FILE)
    st.sidebar.success("✅ To Watch restored!")
    st.rerun()

up_d = st.sidebar.file_uploader("Upload disliked_list.csv", type="csv", key="up_d")
if up_d:
    st.session_state.disliked = pd.read_csv(up_d)
    save_list(st.session_state.disliked, DISLIKED_FILE)
    st.sidebar.success("✅ Disliked restored!")
    st.rerun()

# ====================== FILE STATUS + CLEANUP ======================
st.sidebar.subheader("📁 Current Data")
st.sidebar.write(f"**Watched:** {len(st.session_state.get('watched', []))} movies")
st.sidebar.write(f"**To Watch:** {len(st.session_state.get('to_watch', []))} movies")
st.sidebar.write(f"**Disliked:** {len(st.session_state.get('disliked', []))} movies")

if st.sidebar.button("🧹 Clean Disliked List (remove watched movies)"):
    st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin(st.session_state.watched['title'].tolist())]
    save_list(st.session_state.disliked, DISLIKED_FILE)
    st.sidebar.success("✅ Cleaned! Disliked list updated.")
    st.rerun()

if st.sidebar.button("🔄 Reload from Files"):
    st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
    st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])
    st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])
    st.toast("Reloaded from files", icon="🔄")
    st.rerun()

# Load on startup
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

# ====================== PROFESSIONAL HEADER ======================
st.markdown("""
<div style="background: linear-gradient(90deg, #1e293b, #334155); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #475569;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; color: #60a5fa;">🎥 Brous Movie Dashboard</h1>
            <p style="margin: 5px 0 0 0; color: #94a3b8;">Track • Discover • Enjoy</p>
        </div>
        <div style="text-align: right;">
            <p style="margin: 0; color: #cbd5e1;">Welcome back, Bradlee & Zach!</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ====================== LIVE GLOBAL SEARCH ======================
if 'global_search' not in st.session_state:
    st.session_state.global_search = ""

global_search = st.text_input(
    "🔍 Search recommendations", 
    value=st.session_state.global_search,
    key="global_search_input",
    placeholder="Type instantly - no Enter needed",
    label_visibility="collapsed"
)

if global_search != st.session_state.global_search:
    st.session_state.global_search = global_search
    st.rerun()

# ====================== STATS ======================
st.subheader("📊 Your Stats")

stats_container = st.container()
with stats_container:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #475569; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">🎬</div>
            <div style="font-size: 28px; font-weight: bold; color: #60a5fa;">{}</div>
            <div style="color: #94a3b8; font-size: 14px;">Movies Watched</div>
        </div>
        """.format(len(st.session_state.watched)), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #475569; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">📝</div>
            <div style="font-size: 28px; font-weight: bold; color: #60a5fa;">{}</div>
            <div style="color: #94a3b8; font-size: 14px;">To Watch</div>
        </div>
        """.format(len(st.session_state.to_watch)), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #475569; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">👎</div>
            <div style="font-size: 28px; font-weight: bold; color: #f87171;">{}</div>
            <div style="color: #94a3b8; font-size: 14px;">Disliked</div>
        </div>
        """.format(len(st.session_state.disliked)), unsafe_allow_html=True)
    
    with col4:
        loved_count = len(st.session_state.watched[st.session_state.watched['rating'] == 5.0])
        st.markdown("""
        <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #475569; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">❤️</div>
            <div style="font-size: 28px; font-weight: bold; color: #f87171;">{}</div>
            <div style="color: #94a3b8; font-size: 14px;">Loved / Disliked</div>
        </div>
        """.format(f"{loved_count} / {len(st.session_state.disliked)}"), unsafe_allow_html=True)

st.divider()

# ====================== SIDEBAR ======================
st.sidebar.header("📥 Import from Letterboxd (FIXED)")

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

        current_titles = set(st.session_state.watched['title'].tolist())
        new_movies = []
        skipped = []

        for idx, row in user_df.iterrows():
            title = str(row['title']).strip()
            if title in current_titles:
                continue

            best = search_movie_on_tmdb(title)
            if best is not None:
                rating = row.get('rating')
                if pd.notna(rating) and float(rating) == 5.0:
                    rating = 5.0
                else:
                    rating = None

                new_movies.append({
                    'title': best['title'],
                    'year': best.get('year'),
                    'rating': rating,
                    'matched_id': best.get('id', 999999),
                    'genre': best.get('genre', 'Mixed'),
                    'poster_path': best.get('poster_path')
                })
            else:
                skipped.append(title)

        if new_movies:
            new_df = pd.DataFrame(new_movies)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_list(st.session_state.watched, WATCHED_FILE)
            
            # NEW: Remove from disliked if re-imported
            st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin([m['title'] for m in new_movies])]
            save_list(st.session_state.disliked, DISLIKED_FILE)
            
            st.sidebar.success(f"✅ Added {len(new_movies)} new movies!")
            if skipped:
                st.sidebar.warning(f"Skipped {len(skipped)} movies")
            st.rerun()
        else:
            st.sidebar.info("No new movies to add")

    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# ====================== COUNTS ======================
watched_count = len(st.session_state.watched)
to_watch_count = len(st.session_state.to_watch)

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs([
    "🎯 Recommendations",
    f"📝 To Watch ({to_watch_count})",
    f"📋 Watched ({watched_count})"
])

# ====================== GENRE COLOR MAPPING ======================
genre_colors = {
    "Horror": "#ff6b6b",
    "SciFi": "#4ecdc4",
    "Thriller": "#a855f7",
    "Action": "#f97316",
    "Adventure": "#eab308",
    "Mystery": "#8b5cf6",
    "Fantasy": "#ec4899",
    "Crime": "#ef4444",
    "Drama": "#06b6d4",
    "Comedy": "#22c55e",
    "Mixed": "#6b7280"
}

def get_genre_color(genre):
    return genre_colors.get(genre, "#6b7280")

# ====================== RECOMMENDATIONS TAB ======================
with tab1:
    st.header("🎯 Recommendations For You")
    
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        watched_titles = st.session_state.watched['title'].tolist()
        disliked_titles = st.session_state.disliked['title'].tolist() if len(st.session_state.disliked) > 0 else []
        to_watch_titles = st.session_state.to_watch['title'].tolist() if len(st.session_state.to_watch) > 0 else []
        
        recs = movies_df[~movies_df['title'].isin(watched_titles + disliked_titles + to_watch_titles)].copy()
        
        if st.session_state.global_search:
            recs = recs[recs['title'].str.contains(st.session_state.global_search, case=False, na=False)]
            st.caption(f"🔍 Showing results for: **{st.session_state.global_search}** ({len(recs)} found)")
        
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
        
        vibe_options = [
            "Found Footage", "Supernatural", "Slasher", "Psychological", 
            "Alien / Space", "Dystopian", "Serial Killer", "Mind-Bending",
            "Gore", "Jump Scare", "Slow Burn", "Body Horror", 
            "Cosmic Horror", "Zombie", "Vampire", "Post-Apocalyptic",
            "Time Travel", "AI / Robot", "Survival", "Folk Horror",
            "Funny", "Action"
        ]
        selected_vibes = st.multiselect("Filter by vibe (updates instantly)", vibe_options, default=[], key="vibe_filter")
        
        if selected_vibes:
            keyword_map = {
                "Found Footage": ["found footage", "handheld"],
                "Supernatural": ["supernatural", "ghost", "haunted", "demon"],
                "Slasher": ["slasher", "killer", "blood"],
                "Psychological": ["psychological", "slow burn", "mind"],
                "Alien / Space": ["alien", "space", "planet", "sci-fi"],
                "Dystopian": ["dystopian", "future", "society"],
                "Serial Killer": ["serial", "killer", "murder"],
                "Mind-Bending": ["mind-bending", "twist", "reality"],
                "Gore": ["gore", "blood", "graphic"],
                "Jump Scare": ["jump scare", "sudden"],
                "Slow Burn": ["slow burn", "atmospheric"],
                "Body Horror": ["body horror", "transformation"],
                "Cosmic Horror": ["cosmic", "lovecraft", "eldritch"],
                "Zombie": ["zombie", "undead"],
                "Vampire": ["vampire", "dracula"],
                "Post-Apocalyptic": ["post-apocalyptic", "wasteland"],
                "Time Travel": ["time travel", "time loop"],
                "AI / Robot": ["ai", "robot", "artificial"],
                "Survival": ["survival", "stranded"],
                "Folk Horror": ["folk", "cult", "rural"],
                "Funny": ["funny", "comedy", "humor", "laugh", "hilarious"],
                "Action": ["action", "fight", "chase", "explosion", "shootout", "intense"]
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
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=120)
                    else:
                        st.caption("🎬")
                
                with col2:
                    genre_color = get_genre_color(row.get('genre', 'Mixed'))
                    genre_tag = f"<span style='color: {genre_color}; font-weight: bold;'>[{row.get('genre', 'Mixed')}]</span> "
                    st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})", unsafe_allow_html=True)
                    st.caption(f"TMDB Score: {row.get('vote_average', 'N/A'):.1f}")
                    st.write(str(row['overview'])[:160] + "..." if len(str(row['overview'])) > 160 else row['overview'])
                    
                    col_a, col_b, col_c, col_d = st.columns(4)
                    
                    with col_a:
                        if st.button("❤️ Loved it", key=f"loved_{row.get('id', idx)}", width='stretch'):
                            new_entry = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'rating': 5.0,
                                'matched_id': row.get('id', 999999),
                                'genre': row.get('genre', 'Mixed'),
                                'poster_path': row.get('poster_path')
                            }])
                            st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.watched, WATCHED_FILE)
                            st.toast(f"❤️ Loved {row['title']}!", icon="❤️")
                            st.rerun()
                    
                    with col_b:
                        if st.button("👎 Not Interested", key=f"not_interested_{row.get('id', idx)}", width='stretch'):
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
                    
                    with col_c:
                        if st.button("➕ To Watch", key=f"to_watch_{row.get('id', idx)}", width='stretch'):
                            new_to_watch = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'matched_id': row.get('id', 999999),
                                'genre': row.get('genre', 'Mixed'),
                                'poster_path': row.get('poster_path')
                            }])
                            st.session_state.to_watch = pd.concat([st.session_state.to_watch, new_to_watch]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.to_watch, TO_WATCH_FILE)
                            st.toast(f"Added {row['title']} to To Watch!", icon="📝")
                            st.rerun()
                    
                    with col_d:
                        if st.button("👎 Disliked", key=f"disliked_{row.get('id', idx)}", width='stretch'):
                            new_dislike = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'matched_id': row.get('id', 999999),
                                'genre': row.get('genre', 'Mixed')
                            }])
                            st.session_state.disliked = pd.concat([st.session_state.disliked, new_dislike]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.disliked, DISLIKED_FILE)
                            
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
                            
                            st.toast(f"Added {row['title']} as Disliked", icon="👎")
                            st.rerun()
                
                with st.expander(f"🔍 Details for {row['title']}"):
                    details = get_movie_details(row.get('id', 0))
                    if details:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Runtime:** {details.get('runtime', 'N/A')} min")
                            st.write(f"**Genres:** {', '.join([g['name'] for g in details.get('genres', [])])}")
                        with col2:
                            if details.get('credits') and details['credits'].get('crew'):
                                directors = [p['name'] for p in details['credits']['crew'] if p['job'] == 'Director'][:2]
                                st.write(f"**Director:** {', '.join(directors) if directors else 'N/A'}")
                            
                            if details.get('credits') and details['credits'].get('cast'):
                                cast = [p['name'] for p in details['credits']['cast'][:5]]
                                st.write(f"**Top Cast:** {', '.join(cast)}")
                        
                        imdb_id = details.get('external_ids', {}).get('imdb_id')
                        if imdb_id:
                            st.markdown(f"[🔗 View on IMDB](https://www.imdb.com/title/{imdb_id}/)")
                        st.markdown(f"[🔗 View on TMDB](https://www.themoviedb.org/movie/{row.get('id', 0)})")
                    else:
                        st.caption("Could not load additional details.")
                
                st.divider()

# ====================== TO WATCH TAB ======================
with tab2:
    st.header("📝 To Watch List")
    
    if len(st.session_state.to_watch) > 0:
        cols = st.columns([1, 1, 1, 1])
        
        for idx, (i, row) in enumerate(st.session_state.to_watch.reset_index(drop=True).iterrows()):
            col = cols[idx % 4]
            
            with col:
                with st.container():
                    st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #475569;">
                    """, unsafe_allow_html=True)
                    
                    if pd.notna(row.get('poster_path')):
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=160)
                    else:
                        st.caption("🎬 No poster")
                    
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("❤️ Loved", key=f"tw_loved_{i}", width='stretch'):
                            new_entry = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'rating': 5.0,
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
                        if st.button("👎 Disliked", key=f"tw_disliked_{i}", width='stretch'):
                            new_dislike = pd.DataFrame([{
                                'title': row['title'],
                                'year': row['year'],
                                'matched_id': row.get('matched_id', 999999),
                                'genre': row.get('genre', 'Mixed')
                            }])
                            st.session_state.disliked = pd.concat([st.session_state.disliked, new_dislike]).drop_duplicates(subset=['title'])
                            save_list(st.session_state.disliked, DISLIKED_FILE)
                            
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
                    
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Your To Watch list is empty. Add movies from Recommendations!")

# ====================== WATCHED TAB ======================
with tab3:
    st.header("📋 Watched Movies")
    
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
        cols = st.columns([1, 1, 1, 1])
        
        for idx, (i, row) in enumerate(filtered_watched.reset_index(drop=True).iterrows()):
            col = cols[idx % 4]
            
            with col:
                with st.container():
                    st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #475569;">
                    """, unsafe_allow_html=True)
                    
                    if pd.notna(row.get('poster_path')) and row['poster_path'] != 'None':
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=100)
                    else:
                        st.caption("🎬 No poster")
                    
                    is_disliked = row['title'] in st.session_state.disliked['title'].values
                    is_loved = pd.notna(row.get('rating')) and row['rating'] == 5.0
                    
                    if is_loved:
                        tag = "❤️ <span style='color:#f87171; font-weight:bold;'>Loved</span>"
                    elif is_disliked:
                        tag = "👎 <span style='color:#f87171; font-weight:bold;'>Disliked</span>"
                    else:
                        tag = ""
                    
                    display_genre = row.get('genre', '') if row.get('genre') and row.get('genre') != 'Mixed' else ""
                    genre_color = get_genre_color(row.get('genre', 'Mixed'))
                    genre_tag = f"<span style='color: {genre_color}; font-weight: bold;'>[{display_genre}]</span> " if display_genre else ""
                    
                    rating_text = f" • ⭐ {row['rating']}" if pd.notna(row.get('rating')) else ""
                    st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'}){rating_text} {tag}", unsafe_allow_html=True)
                    
                    if st.button("🗑️ Delete", key=f"del_watched_{row['title']}_{i}", width='stretch'):
                        orig_idx = st.session_state.watched[st.session_state.watched['title'] == row['title']].index[0]
                        st.session_state.watched = st.session_state.watched.drop(orig_idx)
                        save_list(st.session_state.watched, WATCHED_FILE)
                        st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
        
        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("Showing", len(filtered_watched))
        if st.button("Clear All Watched", width='stretch'):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
            save_list(st.session_state.watched, WATCHED_FILE)
            st.rerun()
    else:
        st.info("No movies match your search.")

st.sidebar.caption("Added automatic + manual cleanup for Disliked list")
