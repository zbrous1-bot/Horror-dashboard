import streamlit as st
import pandas as pd
import requests
import os
import random
import json
import altair as alt
from thefuzz import process, fuzz

st.set_page_config(page_title="Brous Movie Dashboard", page_icon="🎥", layout="wide")

# ====================== GLOBAL CONSTANTS (defined early for all tabs) ======================
# This prevents NameError if any tab references them before their original definition point.
genre_colors = {
    "Horror": "#ff6b6b", "SciFi": "#4ecdc4", "Thriller": "#a855f7",
    "Action": "#f97316", "Adventure": "#eab308", "Mystery": "#8b5cf6",
    "Fantasy": "#ec4899", "Crime": "#ef4444", "Drama": "#06b6d4", "Comedy": "#22c55e",
    "Mixed": "#6b7280"
}

def get_genre_color(genre):
    """Safe helper that always returns a fallback color."""
    if 'genre_colors' not in globals() or not isinstance(genre_colors, dict):
        return "#6b7280"
    return genre_colors.get(genre, "#6b7280")

# ====================== GLOBAL CSS ======================
st.markdown("""
<style>
    @media (max-width: 768px) {
        .stApp { font-size: 15px; }
        .stButton button { font-size: 15px !important; padding: 12px 16px !important; height: 48px !important; }
        .stTabs [data-baseweb="tab-list"] button { font-size: 15px !important; padding: 10px 12px !important; }
        
        /* Better mobile card layout */
        .movie-card {
            padding: 12px;
            margin-bottom: 14px;
        }
        
        /* Make recommendation cards stack better */
        .movie-card .stColumn {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        
        /* Recently watched row - horizontal scroll on mobile */
        .recently-watched-row {
            overflow-x: auto;
            white-space: nowrap;
            -webkit-overflow-scrolling: touch;
        }
        
        .recently-watched-row > div {
            display: inline-block;
            margin-right: 8px;
            vertical-align: top;
        }
        
        /* Larger touch targets for mobile */
        .stButton button {
            min-height: 44px !important;
        }
    }
    
    .movie-card {
        background: #1e293b;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 18px;
        border: 1px solid #475569;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    
    .movie-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        border-color: #60a5fa;
    }
    
    .rec-reason {
        font-size: 0.8em;
        color: #94a3b8;
        font-style: italic;
        margin-top: 4px;
    }
    
    .stats-card {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        border: 1px solid #475569;
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
    }
</style>
""", unsafe_allow_html=True)

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
    </style>
    """, unsafe_allow_html=True)

# ====================== GLOBAL SEARCH ======================
if 'global_search' not in st.session_state:
    st.session_state.global_search = ""

# ====================== TMDB KEY ======================
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
    """Wrapper around TMDB requests with basic error handling."""
    url = f"https://api.themoviedb.org/3{endpoint}"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        return None

@st.cache_data(ttl=3600)
def get_movie_details(movie_id):
    """Fetch movie details with caching to reduce API calls."""
    if not movie_id:
        return None
    return tmdb_request(f"/movie/{movie_id}", {"append_to_response": "credits,external_ids"})


def search_movie_on_tmdb(title: str, threshold: int = 78):
    """
    Find the best matching movie using fuzzy matching against the locally loaded catalog.
    Uses thefuzz (already imported). Returns a dict or None.
    """
    if 'movies_df' not in globals() or movies_df.empty:
        return None

    titles = movies_df['title'].dropna().tolist()
    if not titles:
        return None

    # Use WRatio for good balance of partial + full matching
    match = process.extractOne(title, titles, scorer=fuzz.WRatio)

    if match and match[1] >= threshold:
        matched_title = match[0]
        row = movies_df[movies_df['title'] == matched_title].iloc[0]
        return row.to_dict()

    # TODO: Could add a fallback live TMDB search here if no good local match
    return None


# ====================== LOAD MOVIES ======================
@st.cache_data(ttl=3600)
def load_movies():
    genres = {
        27: "Horror", 878: "SciFi", 53: "Thriller",
        28: "Action", 12: "Adventure", 9648: "Mystery",
        14: "Fantasy", 80: "Crime", 18: "Drama", 35: "Comedy"
    }
    all_movies = []
    for genre_id, genre_name in genres.items():
        for page in range(1, 5):
            data = tmdb_request("/discover/movie", {
                "with_genres": str(genre_id),
                "sort_by": "popularity.desc",
                "vote_count.gte": 30,
                "page": page,
                "include_adult": "false",
                "with_original_language": "en"
            })
            if data and 'results' in data:
                for m in data['results']:
                    title = (m.get('title') or m.get('original_title') or "").lower()
                    overview = (m.get('overview') or "").lower()
                    bad_keywords = ["porn", "xxx", "erotic", "adult", "nude", "sex tape", "playboy"]
                    if any(kw in title or kw in overview for kw in bad_keywords):
                        continue
                    
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
    if df.empty:
        return pd.DataFrame(columns=['title', 'year', 'overview', 'vote_average', 'poster_path', 'id', 'genre'])
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
            df = df.dropna(subset=['title'])
            df = df[df['title'].astype(str).str.strip() != '']
            return df
        except Exception as e:
            st.warning(f"Could not load {file}: {e}")
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_list(df, file):
    df.to_csv(file, index=False)


# ====================== DATA HELPERS (reduces massive duplication) ======================

def normalize_movie_record(data: dict) -> dict:
    """Standardize a movie record dict with safe defaults."""
    return {
        'title': data.get('title'),
        'year': data.get('year'),
        'rating': data.get('rating'),
        'matched_id': data.get('matched_id') or data.get('id', 999999),
        'genre': data.get('genre', 'Mixed'),
        'poster_path': data.get('poster_path'),
    }


def add_to_watched(movie_data: dict, rating=None):
    """Safely add a movie to the watched list."""
    record = normalize_movie_record(movie_data)
    if rating is not None:
        record['rating'] = rating

    new_entry = pd.DataFrame([record])
    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
    save_list(st.session_state.watched, WATCHED_FILE)


def add_to_to_watch(movie_data: dict):
    """Safely add a movie to the To Watch list."""
    record = normalize_movie_record(movie_data)
    new_entry = pd.DataFrame([record])
    st.session_state.to_watch = pd.concat([st.session_state.to_watch, new_entry]).drop_duplicates(subset=['title'])
    save_list(st.session_state.to_watch, TO_WATCH_FILE)


def add_to_disliked(movie_data: dict):
    """Safely add a movie to the disliked list."""
    record = normalize_movie_record(movie_data)
    new_entry = pd.DataFrame([record])
    st.session_state.disliked = pd.concat([st.session_state.disliked, new_entry]).drop_duplicates(subset=['title'])
    save_list(st.session_state.disliked, DISLIKED_FILE)


def remove_from_to_watch(title: str):
    """Remove a movie from To Watch list."""
    if 'to_watch' in st.session_state and not st.session_state.to_watch.empty:
        st.session_state.to_watch = st.session_state.to_watch[st.session_state.to_watch['title'] != title]
        save_list(st.session_state.to_watch, TO_WATCH_FILE)


def safe_get_rating(df: pd.DataFrame):
    """Safely count 5-star (loved) movies."""
    if df is None or df.empty or 'rating' not in df.columns:
        return 0
    return int((df['rating'] == 5.0).sum())


def get_star_rating_input(key_prefix="rating", default=5):
    """Nice 1-5 star rating selector."""
    stars = "★" * 5
    rating = st.radio(
        "Your rating",
        options=[1, 2, 3, 4, 5],
        index=default - 1,
        format_func=lambda x: "★" * x + "☆" * (5 - x),
        horizontal=True,
        key=f"{key_prefix}_stars"
    )
    return rating


# ====================== USER TASTE PROFILE & BETTER RECOMMENDATIONS ======================

def get_user_genre_preferences():
    """Calculate user's favorite genres based on watched + loved movies."""
    if st.session_state.watched.empty:
        return {}
    
    # Give extra weight to movies the user "Loved" (rating == 5.0)
    loved = st.session_state.watched[st.session_state.watched['rating'] == 5.0]
    regular = st.session_state.watched[st.session_state.watched['rating'] != 5.0]
    
    genre_counts = {}
    
    for df, weight in [(loved, 3), (regular, 1)]:
        for _, row in df.iterrows():
            genre = row.get('genre', 'Mixed')
            if genre and genre != 'Mixed':
                genre_counts[genre] = genre_counts.get(genre, 0) + weight
    
    # Normalize to percentages
    total = sum(genre_counts.values())
    if total == 0:
        return {}
    
    return {g: round(c / total * 100, 1) for g, c in 
            sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]}


def boost_by_user_taste(df, user_prefs, boost=2.5):
    """Boost movies whose genre matches user's top preferences."""
    if not user_prefs or df.empty:
        return df
    
    top_genres = list(user_prefs.keys())[:3]
    
    def score(row):
        genre = row.get('genre', '')
        base = row.get('vote_average', 0) or 0
        if genre in top_genres:
            return base + boost
        return base
    
    df = df.copy()
    df['taste_score'] = df.apply(score, axis=1)
    return df.sort_values('taste_score', ascending=False)


# ====================== FULL BACKUP SYSTEM (prevents data loss on Streamlit Cloud) ======================

def get_full_backup_json() -> bytes:
    """Export all user data as a single JSON file."""
    backup = {
        "watched": st.session_state.watched.to_dict(orient="records") if not st.session_state.watched.empty else [],
        "to_watch": st.session_state.to_watch.to_dict(orient="records") if not st.session_state.to_watch.empty else [],
        "disliked": st.session_state.disliked.to_dict(orient="records") if not st.session_state.disliked.empty else [],
        "exported_at": pd.Timestamp.now().isoformat(),
        "version": "2.0"
    }
    return json.dumps(backup, indent=2).encode("utf-8")


def load_full_backup(uploaded_file):
    """Load all data from a full JSON backup."""
    try:
        data = json.load(uploaded_file)
        
        if "watched" in data:
            st.session_state.watched = pd.DataFrame(data["watched"])
            save_list(st.session_state.watched, WATCHED_FILE)
        
        if "to_watch" in data:
            st.session_state.to_watch = pd.DataFrame(data["to_watch"])
            save_list(st.session_state.to_watch, TO_WATCH_FILE)
        
        if "disliked" in data:
            st.session_state.disliked = pd.DataFrame(data["disliked"])
            save_list(st.session_state.disliked, DISLIKED_FILE)
        
        return True
    except Exception as e:
        st.error(f"Failed to restore backup: {e}")
        return False


# ====================== BACKUP & RESTORE (IMPORTANT FOR CLOUD) ======================

# Warning for Streamlit Cloud users
st.sidebar.markdown("---")
st.sidebar.warning(
    "⚠️ **Streamlit Cloud Warning**\n\n"
    "This app runs on free-tier Streamlit Cloud. "
    "If the app sleeps due to inactivity, local files can be lost. "
    "**Download a backup regularly!**"
)

st.sidebar.subheader("💾 Full Backup & Restore")

# One-click full backup (recommended)
if st.sidebar.button("📦 Download Full Backup (JSON)", use_container_width=True):
    backup_bytes = get_full_backup_json()
    st.sidebar.download_button(
        label="⬇️ Click to Download Backup",
        data=backup_bytes,
        file_name=f"brous_movie_dashboard_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        use_container_width=True
    )
    st.toast("Backup ready — download it now!", icon="💾")

st.sidebar.caption("One file containing everything. Highly recommended.")

# Single restore uploader (much better UX)
restored_file = st.sidebar.file_uploader(
    "📤 Restore from Full Backup (JSON)",
    type="json",
    key="full_backup_restore"
)
if restored_file:
    if load_full_backup(restored_file):
        st.sidebar.success("✅ Full backup restored successfully!")
        st.toast("All data restored!", icon="✅")
        st.rerun()

# ====================== FILE STATUS ======================
st.sidebar.subheader("📁 Current Data")
st.sidebar.write(f"**Watched:** {len(st.session_state.get('watched', []))} movies")
st.sidebar.write(f"**To Watch:** {len(st.session_state.get('to_watch', []))} movies")
st.sidebar.write(f"**Disliked:** {len(st.session_state.get('disliked', []))} movies")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.sidebar.button("🧹 Clean Disliked", use_container_width=True):
        if not st.session_state.disliked.empty and not st.session_state.watched.empty:
            st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin(st.session_state.watched['title'].tolist())]
            save_list(st.session_state.disliked, DISLIKED_FILE)
            st.sidebar.success("Cleaned!")
            st.rerun()
with col2:
    if st.sidebar.button("🔄 Reload CSVs", use_container_width=True):
        st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
        st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])
        st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])
        st.toast("Reloaded from local CSVs", icon="🔄")
        st.rerun()

st.sidebar.caption("For Cloud users: Use the JSON backup above to avoid data loss.")

# ====================== LOAD DATA ======================
if 'watched' not in st.session_state:
    st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])

if 'to_watch' not in st.session_state:
    st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])

if 'disliked' not in st.session_state:
    st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])

# ====================== HEADER ======================

# Gentle reminder banner (always visible but not too loud)
st.caption("💾 **Tip:** Use the **Full Backup (JSON)** button in the sidebar to protect your data on Streamlit Cloud.")

st.markdown("""
<div style="background: linear-gradient(90deg, #1e293b, #334155); padding: 24px; border-radius: 16px; margin-bottom: 24px; border: 1px solid #475569;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; color: #60a5fa; font-size: 2.2rem;">🎥 Brous Movie Dashboard</h1>
            <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 1.05rem;">Track • Discover • Enjoy</p>
        </div>
        <div style="text-align: right;">
            <p style="margin: 0; color: #cbd5e1; font-weight: 500;">Welcome back, Bradlee & Zach!</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ====================== ENHANCED STATS ======================
st.subheader("📊 Your Stats")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="stats-card">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🎬</div>
        <div style="font-size: 2rem; font-weight: bold; color: #60a5fa;">{}</div>
        <div style="color: #94a3b8; margin-top: 4px;">Movies Watched</div>
    </div>
    """.format(len(st.session_state.watched)), unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="stats-card">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">📝</div>
        <div style="font-size: 2rem; font-weight: bold; color: #60a5fa;">{}</div>
        <div style="color: #94a3b8; margin-top: 4px;">To Watch</div>
    </div>
    """.format(len(st.session_state.to_watch)), unsafe_allow_html=True)

with col3:
    avg_rating = round(st.session_state.watched['rating'].mean(), 1) if not st.session_state.watched.empty and 'rating' in st.session_state.watched.columns else "—"
    st.markdown("""
    <div class="stats-card">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">⭐</div>
        <div style="font-size: 2rem; font-weight: bold; color: #f87171;">{}</div>
        <div style="color: #94a3b8; margin-top: 4px;">Avg Rating</div>
    </div>
    """.format(avg_rating), unsafe_allow_html=True)

st.divider()

# === NEW: Global Cross-List Search ===
with st.expander("🔎 Search All Your Lists", expanded=False):
    search_query = st.text_input("Search across Watched, To Watch, and Disliked", key="global_cross_search")
    
    if search_query:
        all_lists = pd.concat([
            st.session_state.watched.assign(source="Watched"),
            st.session_state.to_watch.assign(source="To Watch"),
            st.session_state.disliked.assign(source="Disliked")
        ], ignore_index=True)
        
        results = all_lists[all_lists['title'].str.contains(search_query, case=False, na=False)]
        
        if not results.empty:
            st.write(f"Found {len(results)} matches:")
            for _, row in results.iterrows():
                st.markdown(f"- **{row['title']}** ({row.get('year', 'N/A')}) — *{row['source']}*")
        else:
            st.info("No matches found.")

# === NEW: Visual Genre Breakdown (UI improvement) ===
if not st.session_state.watched.empty:
    genre_counts = st.session_state.watched['genre'].value_counts().reset_index()
    genre_counts.columns = ['Genre', 'Count']
    
    if len(genre_counts) > 1:
        chart = alt.Chart(genre_counts).mark_bar().encode(
            x=alt.X('Count:Q'),
            y=alt.Y('Genre:N', sort='-x'),
            color=alt.Color('Genre:N', scale=alt.Scale(domain=list(genre_colors.keys()), range=list(genre_colors.values())))
        ).properties(height=200, title="Your Watched Movies by Genre")
        st.altair_chart(chart, use_container_width=True)

    # === NEW: Decade breakdown chart ===
    if not st.session_state.watched.empty:
        watched_copy = st.session_state.watched.copy()
        watched_copy['decade'] = (watched_copy['year'].astype(float) // 10 * 10).astype('Int64')
        decade_counts = watched_copy['decade'].value_counts().reset_index()
        decade_counts.columns = ['Decade', 'Count']
        decade_counts = decade_counts.dropna()
        
        if len(decade_counts) > 1:
            decade_chart = alt.Chart(decade_counts).mark_bar(color='#60a5fa').encode(
                x=alt.X('Decade:O'),
                y='Count:Q'
            ).properties(height=180, title="Movies Watched by Decade")
            st.altair_chart(decade_chart, use_container_width=True)

# ====================== RECENTLY WATCHED (FIXED) ======================
if len(st.session_state.watched) > 0:
    st.subheader("🕒 Recently Watched")
    
    recent = st.session_state.watched.copy()
    recent = recent.dropna(subset=['title'])
    recent['year'] = pd.to_numeric(recent['year'], errors='coerce')
    recent = recent.sort_values('year', ascending=False).head(8).reset_index(drop=True)
    
    st.markdown('<div class="recently-watched-row">', unsafe_allow_html=True)
    cols = st.columns(8)
    
    for idx in range(8):
        with cols[idx]:
            if idx < len(recent):
                row = recent.iloc[idx]
                
                poster = row.get('poster_path')
                if pd.notna(poster) and str(poster).strip() not in ['', 'None', 'nan']:
                    st.image(f"https://image.tmdb.org/t/p/w200{poster}", width=85)
                else:
                    st.caption("🎬")
                
                title = str(row.get('title', 'Unknown Movie'))
                if len(title) > 15:
                    title = title[:15] + "…"
                
                year = row.get('year')
                year_display = f"({int(year)})" if pd.notna(year) else ""
                
                rating = row.get('rating')
                rating_display = ""
                if pd.notna(rating) and rating > 0:
                    rating_display = " " + "★" * int(rating)
                
                st.caption(f"**{title}** {year_display}{rating_display}")
            else:
                st.caption("—")

    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

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

        current_titles = set(st.session_state.watched['title'].tolist())
        new_movies = []

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

        if new_movies:
            for m in new_movies:
                add_to_watched(m, rating=m.get('rating'))

            # Clean up any that were previously disliked
            disliked_titles = set(m['title'] for m in new_movies)
            if not st.session_state.disliked.empty:
                st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin(disliked_titles)]
                save_list(st.session_state.disliked, DISLIKED_FILE)

            st.sidebar.success(f"✅ Added {len(new_movies)} new movies!")
            st.rerun()
        else:
            st.sidebar.info("No new movies to add")

    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# ====================== COUNTS ======================
watched_count = len(st.session_state.watched)
to_watch_count = len(st.session_state.to_watch)

# ====================== TABS ======================
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Recommendations",
    f"📝 To Watch ({to_watch_count})",
    f"📋 Watched ({watched_count})",
    "📊 Stats"
])

# (genre_colors and get_genre_color are now defined at the very top of the file for safety)

# ====================== RECOMMENDATIONS TAB ======================
with tab1:
    st.header("🎯 Recommendations For You")
    
    # === NEW: Your Taste Profile ===
    user_prefs = get_user_genre_preferences()
    if user_prefs:
        with st.expander("🎭 Your Taste Profile (based on what you've loved)", expanded=False):
            cols = st.columns(len(user_prefs))
            for i, (genre, pct) in enumerate(user_prefs.items()):
                with cols[i]:
                    st.metric(genre, f"{pct}%")
            st.caption("Recommendations are now boosted toward your top genres.")


    
    watched_titles = st.session_state.watched['title'].tolist() if len(st.session_state.watched) > 0 else []
    disliked_titles = st.session_state.disliked['title'].tolist() if len(st.session_state.disliked) > 0 else []
    to_watch_titles = st.session_state.to_watch['title'].tolist() if len(st.session_state.to_watch) > 0 else []
    
    # Normalize titles for reliable matching (handles case, extra spaces, Letterboxd vs TMDB differences)
    def _norm_title(t):
        if pd.isna(t) or t is None:
            return ""
        return str(t).strip().lower()
    
    watched_norm = [_norm_title(t) for t in watched_titles]
    disliked_norm = [_norm_title(t) for t in disliked_titles]
    to_watch_norm = [_norm_title(t) for t in to_watch_titles]
    
    recs = movies_df[~movies_df['title'].apply(_norm_title).isin(watched_norm + disliked_norm + to_watch_norm)].copy()
    
    # === NEW: Recommendation Filters ===
    with st.expander("🔍 Filter Recommendations", expanded=False):
        fcol1, fcol2, fcol3 = st.columns(3)
        
        with fcol1:
            min_year = st.slider("Min Year", 1950, 2026, 1980, step=5, key="rec_min_year")
        with fcol2:
            min_rating = st.slider("Min TMDB Score", 0.0, 10.0, 6.0, step=0.5, key="rec_min_score")
        with fcol3:
            available_genres = sorted(recs['genre'].dropna().unique().tolist())
            selected_genres = st.multiselect("Genres", available_genres, default=[], key="rec_genres")
        
        hidden_gems = st.checkbox("✨ Hidden Gems mode (lower popularity, high match to your taste)", key="hidden_gems")
    
    # Apply filters
    if 'year' in recs.columns:
        recs = recs[recs['year'].astype(float, errors='ignore') >= min_year]
    recs = recs[recs['vote_average'].astype(float, errors='ignore') >= min_rating]
    if selected_genres:
        recs = recs[recs['genre'].isin(selected_genres)]
    
    # Hidden Gems filter (lower TMDB score but still good, or we can use vote count as proxy for popularity)
    if hidden_gems:
        recs = recs[recs['vote_average'].astype(float, errors='ignore') >= 6.5]
        # Sort by score descending but prefer lower "popularity" feel — simple proxy: prefer mid-tier scores
        recs = recs.sort_values('vote_average', ascending=True)
    
    # === NEW: Personalization using user's taste ===
    user_prefs = get_user_genre_preferences()
    
    if user_prefs:
        recs = boost_by_user_taste(recs, user_prefs)
    
    # === Deeper diversity: limit consecutive same-genre movies ===
    if len(recs) > 6:
        diversified = []
        last_genre = None
        genre_streak = 0
        max_streak = 2
        
        for _, row in recs.iterrows():
            g = row.get('genre', 'Mixed')
            if g == last_genre:
                genre_streak += 1
            else:
                genre_streak = 1
                last_genre = g
            
            if genre_streak <= max_streak:
                diversified.append(row)
            if len(diversified) >= 15:
                break
        
        if len(diversified) > 0:
            recs = pd.DataFrame(diversified)
    
    if st.session_state.global_search:
        recs = recs[recs['title'].str.contains(st.session_state.global_search, case=False, na=False)]
        st.caption(f"🔍 Showing results for: **{st.session_state.global_search}** ({len(recs)} found)")
    
    if len(st.session_state.watched) > 0:
        random_watched = st.session_state.watched.sample(1).iloc[0]
        similar_data = tmdb_request(f"/movie/{random_watched['matched_id']}/similar", {"page": 1})
        if similar_data and 'results' in similar_data:
            similar_movies = []
            watched_title = random_watched.get('title', 'a movie you watched')
            for m in similar_data['results'][:8]:
                similar_movies.append({
                    'title': m.get('title') or m.get('original_title'),
                    'year': m.get('release_date', '')[:4] if m.get('release_date') else None,
                    'overview': m.get('overview', ''),
                    'vote_average': m.get('vote_average'),
                    'poster_path': m.get('poster_path'),
                    'id': m.get('id'),
                    'genre': 'Mixed',
                    'source': f"similar_to_{watched_title}"
                })
            similar_df = pd.DataFrame(similar_movies)
            recs = pd.concat([recs, similar_df]).drop_duplicates(subset=['title'])
            if user_prefs:
                recs = boost_by_user_taste(recs, user_prefs)
    
    # === Surprise Me (placed after recs is fully built) ===
    if len(recs) > 0:
        if st.button("🎲 Surprise Me (Pick something good for me)", width='stretch'):
            surprise = recs.sample(1).iloc[0].to_dict()
            st.session_state.surprise_pick = surprise
            st.rerun()
    
    if 'surprise_pick' in st.session_state:
        sp = st.session_state.surprise_pick
        st.success(f"🎲 Surprise Pick: **{sp['title']}** ({sp.get('year', 'N/A')})")
        st.caption(sp.get('overview', '')[:200] + "...")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("➕ Add to To Watch", key="surprise_towatch"):
                add_to_to_watch(sp)
                del st.session_state.surprise_pick
                st.rerun()
        with c2:
            if st.button("⭐ Rate & Loved", key="surprise_loved"):
                with st.popover("Rate it"):
                    r = get_star_rating_input(key_prefix="surprise_rate")
                    if st.button("Save"):
                        add_to_watched(sp, rating=r)
                        del st.session_state.surprise_pick
                        st.rerun()
        with c3:
            if st.button("❌ Not for me", key="surprise_no"):
                del st.session_state.surprise_pick
                st.rerun()
        st.divider()
    
    # Mood Selector
    st.subheader("😌 How are you feeling tonight?")
    
    mood_options = {
        "Feeling spooky 👻": ["supernatural", "ghost", "haunted", "demon", "spirit", "possession", "witch", "curse"],
        "Want something funny 😂": ["funny", "comedy", "humor", "hilarious", "laugh", "sarcastic", "witty"],
        "Mind-bending night 🌀": ["mind-bending", "twist", "psychological", "reality", "surreal", "dream"],
        "Cozy horror 🕯️": ["slow burn", "atmospheric", "folk", "rural", "quiet", "eerie", "dread"],
        "Action-packed 🔥": ["action", "fight", "chase", "explosion", "shootout", "intense", "battle"],
        "Cosmic horror 🌌": ["cosmic", "lovecraft", "eldritch", "space", "alien", "void", "ancient"]
    }
    
    selected_mood = st.selectbox("Choose your mood", list(mood_options.keys()), index=0)
    
    if st.button("🎯 Get Recommendations for this Mood", width='stretch'):
        keywords = mood_options[selected_mood]
        mood_recs = recs[recs['overview'].str.contains('|'.join(keywords), case=False, na=False)]
        
        # Apply taste boosting and current filters to mood results
        if user_prefs:
            mood_recs = boost_by_user_taste(mood_recs, user_prefs)
        
        st.session_state.mood_recommendations = mood_recs.head(8).to_dict('records')
        st.rerun()
    
    if 'mood_recommendations' in st.session_state:
        st.subheader(f"Recommendations for: {selected_mood}")
        for movie in st.session_state.mood_recommendations:
            col1, col2 = st.columns([1, 4])
            with col1:
                if pd.notna(movie.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{movie['poster_path']}", width=80)
            with col2:
                st.markdown(f"**{movie['title']}** ({movie['year']})")
                st.caption(movie['overview'][:140] + "...")
                if st.button(f"➕ Add to To Watch", key=f"mood_add_{movie['id']}"):
                    add_to_to_watch(movie)
                    st.toast(f"Added {movie['title']} to To Watch!", icon="📝")
                    st.rerun()
                if st.button(f"⭐ Rate & Loved", key=f"mood_love_{movie['id']}"):
                    with st.popover("Rate this movie"):
                        rating = get_star_rating_input(key_prefix=f"mood_love_{movie['id']}")
                        if st.button("Save", key=f"mood_save_love_{movie['id']}"):
                            add_to_watched(movie, rating=rating)
                            st.toast(f"Added {movie['title']} with {rating}★", icon="⭐")
                            st.rerun()
        if st.button("Clear Mood Recommendations"):
            del st.session_state.mood_recommendations
            st.rerun()
    
    st.divider()
    
    # Smart Picker
    with st.expander("🎯 What to Watch Tonight? (Smart Picker)", expanded=False):
        st.write("Answer a few questions and I'll pick the best movie for you!")
        
        time_choice = st.radio("How much time do you have?", 
                              ["Short (< 90 min)", "Medium (90-120 min)", "Long (> 120 min)"], 
                              horizontal=True)
        
        mood_choice = st.selectbox("What kind of mood are you in?", 
                                  ["Scary / Horror", "Funny / Light", "Thought-provoking", 
                                   "Action / Thrilling", "Cozy / Atmospheric", "Mind-bending"])
        
        if st.button("🎲 Find My Perfect Movie", width='stretch'):
            filtered = recs.copy()
            
            if "Horror" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("horror|scary|ghost|demon|supernatural", case=False, na=False)]
            elif "Funny" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("funny|comedy|humor|laugh|hilarious", case=False, na=False)]
            elif "Action" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("action|fight|chase|explosion|shootout", case=False, na=False)]
            elif "Mind-bending" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("mind|twist|psychological|reality|surreal", case=False, na=False)]
            elif "Cozy" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("slow burn|atmospheric|folk|rural|quiet", case=False, na=False)]
            elif "Thought-provoking" in mood_choice:
                filtered = filtered[filtered['overview'].str.contains("philosophical|deep|thought|existential|moral", case=False, na=False)]
            
            if len(filtered) > 0:
                filtered = filtered.copy()
                
                # Apply taste profile boosting
                if user_prefs:
                    filtered = boost_by_user_taste(filtered, user_prefs, boost=3.0)
                
                # Scoring
                filtered['score'] = 0
                filtered.loc[filtered['year'].astype(float) >= 2015, 'score'] += 2
                filtered.loc[filtered['year'].astype(float) >= 2020, 'score'] += 1
                filtered.loc[filtered['vote_average'] >= 7.0, 'score'] += 3
                filtered.loc[filtered['vote_average'] >= 7.5, 'score'] += 2
                
                if "Short" in time_choice:
                    filtered = filtered[filtered['vote_average'] > 6.0]
                elif "Long" in time_choice:
                    filtered.loc[filtered['vote_average'] >= 7.0, 'score'] += 2
                
                top_picks = filtered.sort_values('score', ascending=False).head(3)
                st.session_state.smart_picks = top_picks.to_dict('records')
                st.rerun()
            else:
                st.warning("Couldn't find a good match. Try different options!")
    
    if 'smart_picks' in st.session_state:
        st.subheader("🎯 Here are your top picks:")
        
        for i, pick in enumerate(st.session_state.smart_picks):
            col1, col2 = st.columns([1, 4])
            with col1:
                if pd.notna(pick.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{pick['poster_path']}", width=90)
            with col2:
                st.markdown(f"**{pick['title']}** ({pick['year']})")
                st.caption(pick['overview'][:160] + "...")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"➕ Add to To Watch", key=f"smart_add_{i}"):
                        add_to_to_watch(pick)
                        del st.session_state.smart_picks
                        st.rerun()
                with col_b:
                    if st.button(f"⭐ Rate & Loved", key=f"smart_love_{i}"):
                        with st.popover("Rate this movie"):
                            rating = get_star_rating_input(key_prefix=f"smart_love_{i}")
                            if st.button("Save", key=f"smart_save_love_{i}"):
                                add_to_watched(pick, rating=rating)
                                del st.session_state.smart_picks
                                st.rerun()
        
        if st.button("Clear Picks"):
            del st.session_state.smart_picks
            st.rerun()
    
    st.divider()
    
    # Regular Recommendations
    if len(st.session_state.watched) == 0:
        st.info("👋 Start by adding some movies you've watched in the sidebar!")
    else:
        recs = recs.head(15)
        
        # === NEW: Add "Why recommended" reasons (deeper logic) ===
        recs = recs.copy()
        recs['reason'] = ""
        
        top_genres = list(user_prefs.keys())[:3] if user_prefs else []
        
        for i, row in recs.iterrows():
            reason = ""
            genre = row.get('genre', 'Mixed')
            
            if genre in top_genres:
                reason = f"Recommended because you love {genre}"
            elif str(row.get('source', '')).startswith('similar_to_'):
                base = row['source'].replace('similar_to_', '')
                reason = f"Because you watched **{base}**"
            
            recs.at[i, 'reason'] = reason
        
        # Add some diversity - avoid too many from the same top genre
        if len(recs) > 8 and top_genres:
            diversified = []
            genre_counts = {g: 0 for g in top_genres}
            max_per_genre = 4
            
            for _, row in recs.iterrows():
                g = row.get('genre')
                if g in top_genres and genre_counts.get(g, 0) >= max_per_genre:
                    continue
                if g in top_genres:
                    genre_counts[g] = genre_counts.get(g, 0) + 1
                diversified.append(row)
                if len(diversified) >= 15:
                    break
            
            if diversified:
                recs = pd.DataFrame(diversified)
        
        for idx, row in recs.iterrows():
            with st.container():
                st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 5])
                
                with col1:
                    if pd.notna(row.get('poster_path')):
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=100)
                    else:
                        st.caption("🎬")
                
                with col2:
                    genre_color = get_genre_color(row.get('genre', 'Mixed'))
                    genre_tag = f"<span style='color: {genre_color}; font-weight: bold;'>[{row.get('genre', 'Mixed')}]</span> "
                    st.markdown(f"**{genre_tag}{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})", unsafe_allow_html=True)
                    st.caption(f"TMDB Score: {row.get('vote_average', 'N/A'):.1f}")
                    
                    # Show personalized reason when available
                    if row.get('reason'):
                        st.markdown(f"<div class='rec-reason'>✨ {row['reason']}</div>", unsafe_allow_html=True)
                    
                    st.write(str(row['overview'])[:140] + "..." if len(str(row['overview'])) > 140 else row['overview'])
                    
                    # Action buttons - 2x2 grid on mobile, 4 columns on desktop
                    btn_col1, btn_col2 = st.columns(2)
                    
                    with btn_col1:
                        if st.button("✅ Mark as Watched", key=f"watched_{row.get('id', idx)}", width='stretch'):
                            # Direct add with default rating for quick action
                            add_to_watched(row, rating=3)
                            
                            # Also remove from To Watch if it's there
                            if not st.session_state.to_watch.empty:
                                st.session_state.to_watch = st.session_state.to_watch[
                                    st.session_state.to_watch['title'] != row.get('title')
                                ]
                                save_list(st.session_state.to_watch, TO_WATCH_FILE)
                            
                            st.toast(f"Marked {row['title']} as watched", icon="✅")
                            st.rerun()
                    
                        if st.button("👎 Disliked", key=f"disliked_{row.get('id', idx)}", width='stretch'):
                            add_to_disliked(row)
                            add_to_watched(row, rating=None)
                            st.toast(f"Added {row['title']} as Disliked", icon="👎")
                            st.rerun()
                    
                    with btn_col2:
                        if st.button("➕ To Watch", key=f"to_watch_{row.get('id', idx)}", width='stretch'):
                            add_to_to_watch(row)
                            st.toast(f"Added {row['title']} to To Watch!", icon="📝")
                            st.rerun()
                    
                        if st.button("👎 Not Interested", key=f"not_interested_{row.get('id', idx)}", width='stretch'):
                            add_to_disliked(row)
                            st.toast(f"Got it — won't show again", icon="👎")
                            st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                
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

# === NEW: Re-watch Suggestions (Highly Rated) ===
high_rated = st.session_state.watched[
    (st.session_state.watched['rating'].astype(float, errors='ignore') >= 4.0)
].copy()

if not high_rated.empty:
    st.subheader("🔥 Re-watch Suggestions")
    st.caption("Movies you've rated highly — perfect for a re-watch")
    
    rewatch_sample = high_rated.sample(min(4, len(high_rated)))
    
    cols = st.columns(4)
    for i, (_, movie) in enumerate(rewatch_sample.iterrows()):
        with cols[i]:
            if pd.notna(movie.get('poster_path')):
                st.image(f"https://image.tmdb.org/t/p/w200{movie['poster_path']}", width=90)
            else:
                st.caption("🎬")
            
            st.markdown(f"**{movie['title']}** ({int(movie['year']) if pd.notna(movie['year']) else 'N/A'})")
            rating = movie.get('rating')
            if pd.notna(rating):
                st.caption("★" * int(rating))
            
            if st.button("➕ Add to To Watch", key=f"rewatch_{movie.get('id', i)}", width='stretch'):
                add_to_to_watch(movie.to_dict())
                st.toast(f"Added {movie['title']} to To Watch again!", icon="🔥")
                st.rerun()

# ====================== TO WATCH TAB ======================
with tab2:
    st.header("📝 To Watch List")
    
    if len(st.session_state.to_watch) == 0:
        st.info("📭 Your To Watch list is empty. Add movies from the Recommendations tab!")
    else:
        if st.button("🎲 Pick Random Movie", width='stretch'):
            random_movie = st.session_state.to_watch.sample(1).iloc[0]
            st.session_state.random_pick = random_movie
            st.rerun()
        
        if 'random_pick' in st.session_state:
            rm = st.session_state.random_pick
            st.success(f"🎲 Random Pick: **{rm['title']}** ({rm['year']})")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("⭐ Rate & Mark Watched", key="random_loved"):
                    with st.popover("Rate this movie"):
                        rating = get_star_rating_input(key_prefix="random_rate")
                        if st.button("Save & Mark Watched", key="save_random_rate"):
                            add_to_watched(rm, rating=rating)
                            remove_from_to_watch(rm['title'])
                            del st.session_state.random_pick
                            st.rerun()
            with col2:
                if st.button("👎 Disliked", key="random_disliked"):
                    add_to_disliked(rm)
                    add_to_watched(rm, rating=None)
                    remove_from_to_watch(rm['title'])
                    del st.session_state.random_pick
                    st.rerun()
            with col3:
                if st.button("❌ Cancel", key="random_cancel"):
                    del st.session_state.random_pick
                    st.rerun()
        
        cols = st.columns(2)
        for idx, (i, row) in enumerate(st.session_state.to_watch.reset_index(drop=True).iterrows()):
            col = cols[idx % 2]
            with col:
                st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                
                if pd.notna(row.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=140)
                else:
                    st.caption("🎬 No poster")
                
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("⭐ Rate & Watched", key=f"tw_loved_{i}", width='stretch'):
                        with st.popover("Rate this movie"):
                            rating = get_star_rating_input(key_prefix=f"tw_rate_{i}")
                            if st.button("Save Rating", key=f"save_tw_rate_{i}"):
                                add_to_watched(row, rating=rating)
                                st.session_state.to_watch = st.session_state.to_watch.drop(i)
                                save_list(st.session_state.to_watch, TO_WATCH_FILE)
                                st.rerun()
                with col_b:
                    if st.button("👎 Disliked", key=f"tw_disliked_{i}", width='stretch'):
                        add_to_disliked(row)
                        add_to_watched(row, rating=None)
                        st.session_state.to_watch = st.session_state.to_watch.drop(i)
                        save_list(st.session_state.to_watch, TO_WATCH_FILE)
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)

# ====================== WATCHED TAB ======================
with tab3:
    st.header("📋 Watched Movies")
    
    if len(st.session_state.watched) == 0:
        st.info("📭 You haven't added any movies yet. Start by importing from Letterboxd or adding manually!")
    else:
        col1, col2 = st.columns([3, 2])
        with col1:
            search_term = st.text_input("🔍 Search watched movies", key="watched_search")
        with col2:
            sort_option = st.selectbox("Sort by", ["Recently Added", "Year (Newest)", "Year (Oldest)", "Rating (High to Low)", "Title A-Z"], key="watched_sort")

        all_genres = sorted(st.session_state.watched['genre'].dropna().unique().tolist())
        selected_genres = st.multiselect("Filter by Genre", all_genres, default=[], key="watched_genre_filter")

        filtered_watched = st.session_state.watched.copy()
        
        if selected_genres:
            filtered_watched = filtered_watched[filtered_watched['genre'].isin(selected_genres)]
        
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
            cols = st.columns(2)
            
            for idx, (i, row) in enumerate(filtered_watched.reset_index(drop=True).iterrows()):
                col = cols[idx % 2]
                
                with col:
                    st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                    
                    if pd.notna(row.get('poster_path')) and str(row.get('poster_path')) != 'None':
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=90)
                    else:
                        st.caption("🎬 No poster")
                    
                    title = row.get('title', 'Unknown')
                    year = int(row['year']) if pd.notna(row.get('year')) else 'N/A'
                    
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
                    st.markdown(f"**{genre_tag}{title}** ({year}){rating_text} {tag}", unsafe_allow_html=True)
                    
                    if st.button("🗑️ Delete", key=f"del_watched_{title}_{i}", width='stretch'):
                        mask = st.session_state.watched['title'] == title
                        if mask.any():
                            orig_idx = st.session_state.watched[mask].index[0]
                            st.session_state.watched = st.session_state.watched.drop(orig_idx)
                            save_list(st.session_state.watched, WATCHED_FILE)
                            st.rerun()
                        else:
                            st.warning("Movie not found")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.divider()
            col1, col2 = st.columns(2)
            col1.metric("Showing", len(filtered_watched))
            if st.button("Clear All Watched", width='stretch'):
                st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
                save_list(st.session_state.watched, WATCHED_FILE)
                st.rerun()
        else:
            st.info("No movies match your search.")

# ====================== STATS TAB (Dedicated & Enhanced) ======================
with tab4:
    st.header("📊 Your Stats & Insights")
    
    # ====================== SAFE DATA ACCESS ======================
    # These guards prevent the entire Stats tab from crashing if data is missing or malformed
    watched_df = st.session_state.get("watched", pd.DataFrame())
    to_watch_df = st.session_state.get("to_watch", pd.DataFrame())
    disliked_df = st.session_state.get("disliked", pd.DataFrame())
    
    # Ensure expected columns exist to avoid KeyErrors
    for df in [watched_df, to_watch_df, disliked_df]:
        if not df.empty:
            for col in ['title', 'year', 'rating', 'genre']:
                if col not in df.columns:
                    df[col] = None
    
    # ====================== SUMMARY METRICS ======================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Movies Watched", len(watched_df) if not watched_df.empty else 0)
    with col2:
        st.metric("In To Watch", len(to_watch_df) if not to_watch_df.empty else 0)
    with col3:
        try:
            avg_r = round(watched_df['rating'].mean(), 2) if not watched_df.empty and 'rating' in watched_df.columns else "—"
        except Exception:
            avg_r = "—"
        st.metric("Average Rating", avg_r)
    with col4:
        try:
            loved = safe_get_rating(watched_df)
        except Exception:
            loved = 0
        st.metric("Loved (5★)", loved)
    
    st.divider()
    
    # ====================== GENRE BREAKDOWN ======================
    st.subheader("Genre Breakdown")
    
    try:
        if not watched_df.empty and 'genre' in watched_df.columns:
            genre_counts = watched_df['genre'].value_counts().reset_index()
            genre_counts.columns = ['Genre', 'Count']
            
            # Safe access to genre_colors
            domain = list(genre_colors.keys()) if 'genre_colors' in globals() else None
            range_colors = list(genre_colors.values()) if 'genre_colors' in globals() else None
            
            chart_kwargs = {}
            if domain and range_colors:
                chart_kwargs['color'] = alt.Color('Genre:N', scale=alt.Scale(domain=domain, range=range_colors))
            
            genre_chart = alt.Chart(genre_counts).mark_bar().encode(
                x=alt.X('Count:Q'),
                y=alt.Y('Genre:N', sort='-x'),
                **chart_kwargs
            ).properties(height=280)
            st.altair_chart(genre_chart, use_container_width=True)
        else:
            st.info("Watch some movies to see your genre breakdown.")
    except Exception as e:
        st.warning(f"Could not render genre chart: {e}")
    
    # ====================== DECADE DISTRIBUTION ======================
    st.subheader("Decade Distribution")
    
    try:
        if not watched_df.empty and 'year' in watched_df.columns:
            watched_copy = watched_df.copy()
            watched_copy['decade'] = (watched_copy['year'].astype(float, errors='ignore') // 10 * 10).astype('Int64')
            decade_counts = watched_copy['decade'].value_counts().reset_index()
            decade_counts.columns = ['Decade', 'Count']
            decade_counts = decade_counts.dropna().sort_values('Decade')
            
            if not decade_counts.empty:
                decade_chart = alt.Chart(decade_counts).mark_bar(color='#60a5fa').encode(
                    x=alt.X('Decade:O'),
                    y='Count:Q'
                ).properties(height=220)
                st.altair_chart(decade_chart, use_container_width=True)
            else:
                st.info("Not enough year data yet.")
        else:
            st.info("Add some watched movies with year information to see decade distribution.")
    except Exception as e:
        st.warning(f"Could not render decade chart: {e}")
    
    # ====================== RATING DISTRIBUTION ======================
    st.subheader("Rating Distribution")
    
    try:
        if not watched_df.empty and 'rating' in watched_df.columns:
            rated = watched_df[watched_df['rating'].notna()].copy()
            if not rated.empty:
                rating_counts = rated['rating'].value_counts().reindex([1,2,3,4,5], fill_value=0).reset_index()
                rating_counts.columns = ['Rating', 'Count']
                
                rating_chart = alt.Chart(rating_counts).mark_bar(color='#f87171').encode(
                    x=alt.X('Rating:O'),
                    y='Count:Q'
                ).properties(height=200, title="How you rate movies (1 = lowest, 5 = highest)")
                st.altair_chart(rating_chart, use_container_width=True)
            else:
                st.info("Rate some movies (using the star selector) to see your rating distribution.")
        else:
            st.info("Rate some movies to see your rating distribution.")
    except Exception as e:
        st.warning(f"Could not render rating distribution: {e}")
    
    st.divider()
    st.caption("Tip: Download a full JSON backup regularly from the sidebar to protect your data on Streamlit Cloud.")
