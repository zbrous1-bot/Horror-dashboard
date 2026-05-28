import streamlit as st
import pandas as pd
import requests
import os
import random
from thefuzz import process, fuzz

st.set_page_config(page_title="Brous Movie Dashboard", page_icon="🎥", layout="wide")

# ====================== MOBILE CSS ======================
st.markdown("""
<style>
    @media (max-width: 768px) {
        .stApp { font-size: 15px; }
        .stButton button { font-size: 15px !important; padding: 12px 16px !important; height: 48px !important; }
        .stTabs [data-baseweb="tab-list"] button { font-size: 15px !important; padding: 10px 12px !important; }
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
    url = f"https://api.themoviedb.org/3{endpoint}"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.status_code == 200 else None

def get_movie_details(movie_id):
    return tmdb_request(f"/movie/{movie_id}", {"append_to_response": "credits,external_ids"})

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
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_list(df, file):
    df.to_csv(file, index=False)

# ====================== BACKUP & RESTORE ======================
st.sidebar.subheader("💾 Backup & Restore")

if st.sidebar.button("📥 Download Watched"):
    if len(st.session_state.get('watched', [])) > 0:
        st.download_button("Download watched_list.csv", st.session_state.watched.to_csv(index=False), "watched_list.csv", "text/csv")

if st.sidebar.button("📥 Download To Watch"):
    if len(st.session_state.get('to_watch', [])) > 0:
        st.download_button("Download to_watch_list.csv", st.session_state.to_watch.to_csv(index=False), "to_watch_list.csv", "text/csv")

if st.sidebar.button("📥 Download Disliked"):
    if len(st.session_state.get('disliked', [])) > 0:
        st.download_button("Download disliked_list.csv", st.session_state.disliked.to_csv(index=False), "disliked_list.csv", "text/csv")

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

# ====================== FILE STATUS ======================
st.sidebar.subheader("📁 Current Data")
st.sidebar.write(f"**Watched:** {len(st.session_state.get('watched', []))} movies")
st.sidebar.write(f"**To Watch:** {len(st.session_state.get('to_watch', []))} movies")
st.sidebar.write(f"**Disliked:** {len(st.session_state.get('disliked', []))} movies")

if st.sidebar.button("🧹 Clean Disliked List"):
    st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin(st.session_state.watched['title'].tolist())]
    save_list(st.session_state.disliked, DISLIKED_FILE)
    st.sidebar.success("✅ Cleaned!")
    st.rerun()

if st.sidebar.button("🔄 Reload from Files"):
    st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])
    st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])
    st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])
    st.toast("Reloaded from files", icon="🔄")
    st.rerun()

# ====================== LOAD DATA ON STARTUP ======================
if 'watched' not in st.session_state:
    st.session_state.watched = load_list(WATCHED_FILE, ['title', 'year', 'rating', 'matched_id', 'genre', 'poster_path'])

if 'to_watch' not in st.session_state:
    st.session_state.to_watch = load_list(TO_WATCH_FILE, ['title', 'year', 'matched_id', 'genre', 'poster_path'])

if 'disliked' not in st.session_state:
    st.session_state.disliked = load_list(DISLIKED_FILE, ['title', 'year', 'matched_id', 'genre'])

# ====================== HEADER ======================
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

# ====================== STATS ======================
st.subheader("📊 Your Stats")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Movies Watched", len(st.session_state.watched))
with col2:
    st.metric("To Watch", len(st.session_state.to_watch))
with col3:
    loved = len(st.session_state.watched[st.session_state.watched['rating'] == 5.0])
    st.metric("Loved / Disliked", f"{loved} / {len(st.session_state.disliked)}")

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
            new_df = pd.DataFrame(new_movies)
            st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
            save_list(st.session_state.watched, WATCHED_FILE)
            
            st.session_state.disliked = st.session_state.disliked[~st.session_state.disliked['title'].isin([m['title'] for m in new_movies])]
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
tab1, tab2, tab3 = st.tabs([
    "🎯 Recommendations",
    f"📝 To Watch ({to_watch_count})",
    f"📋 Watched ({watched_count})"
])

# ====================== GENRE COLORS ======================
genre_colors = {
    "Horror": "#ff6b6b", "SciFi": "#4ecdc4", "Thriller": "#a855f7",
    "Action": "#f97316", "Adventure": "#eab308", "Mystery": "#8b5cf6",
    "Fantasy": "#ec4899", "Crime": "#ef4444", "Drama": "#06b6d4", "Comedy": "#22c55e",
    "Mixed": "#6b7280"
}

def get_genre_color(genre):
    return genre_colors.get(genre, "#6b7280")

# ====================== RECOMMENDATIONS TAB ======================
with tab1:
    st.header("🎯 Recommendations For You")
    
    watched_titles = st.session_state.watched['title'].tolist() if len(st.session_state.watched) > 0 else []
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
                    new_to_watch = pd.DataFrame([{
                        'title': movie['title'],
                        'year': movie['year'],
                        'matched_id': movie.get('id', 999999),
                        'genre': movie.get('genre', 'Mixed'),
                        'poster_path': movie.get('poster_path')
                    }])
                    st.session_state.to_watch = pd.concat([st.session_state.to_watch, new_to_watch]).drop_duplicates(subset=['title'])
                    save_list(st.session_state.to_watch, TO_WATCH_FILE)
                    st.toast(f"Added {movie['title']} to To Watch!", icon="📝")
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
                        new_to_watch = pd.DataFrame([{
                            'title': pick['title'],
                            'year': pick['year'],
                            'matched_id': pick.get('id', 999999),
                            'genre': pick.get('genre', 'Mixed'),
                            'poster_path': pick.get('poster_path')
                        }])
                        st.session_state.to_watch = pd.concat([st.session_state.to_watch, new_to_watch]).drop_duplicates(subset=['title'])
                        save_list(st.session_state.to_watch, TO_WATCH_FILE)
                        del st.session_state.smart_picks
                        st.rerun()
                with col_b:
                    if st.button(f"❤️ Loved it", key=f"smart_love_{i}"):
                        new_entry = pd.DataFrame([{
                            'title': pick['title'],
                            'year': pick['year'],
                            'rating': 5.0,
                            'matched_id': pick.get('id', 999999),
                            'genre': pick.get('genre', 'Mixed'),
                            'poster_path': pick.get('poster_path')
                        }])
                        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                        save_list(st.session_state.watched, WATCHED_FILE)
                        del st.session_state.smart_picks
                        st.rerun()
        
        if st.button("Clear Picks"):
            del st.session_state.smart_picks
            st.rerun()
    
    st.divider()
    
    # Regular Recommendations
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        recs = recs.head(15)
        
        for idx, row in recs.iterrows():
            with st.container():
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
                    st.write(str(row['overview'])[:140] + "..." if len(str(row['overview'])) > 140 else row['overview'])
                    
                    col_a, col_b = st.columns(2)
                    
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
                    
                    col_c, col_d = st.columns(2)
                    
                    with col_c:
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
                    
                    with col_d:
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
        if st.button("🎲 Pick Random Movie", width='stretch'):
            random_movie = st.session_state.to_watch.sample(1).iloc[0]
            st.session_state.random_pick = random_movie
            st.rerun()
        
        if 'random_pick' in st.session_state:
            rm = st.session_state.random_pick
            st.success(f"🎲 Random Pick: **{rm['title']}** ({rm['year']})")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("❤️ Loved it", key="random_loved"):
                    new_entry = pd.DataFrame([{
                        'title': rm['title'],
                        'year': rm['year'],
                        'rating': 5.0,
                        'matched_id': rm.get('matched_id', 999999),
                        'genre': rm.get('genre', 'Mixed'),
                        'poster_path': rm.get('poster_path')
                    }])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                    save_list(st.session_state.watched, WATCHED_FILE)
                    st.session_state.to_watch = st.session_state.to_watch[st.session_state.to_watch['title'] != rm['title']]
                    save_list(st.session_state.to_watch, TO_WATCH_FILE)
                    del st.session_state.random_pick
                    st.rerun()
            with col2:
                if st.button("👎 Disliked", key="random_disliked"):
                    new_dislike = pd.DataFrame([{
                        'title': rm['title'],
                        'year': rm['year'],
                        'matched_id': rm.get('matched_id', 999999),
                        'genre': rm.get('genre', 'Mixed')
                    }])
                    st.session_state.disliked = pd.concat([st.session_state.disliked, new_dislike]).drop_duplicates(subset=['title'])
                    save_list(st.session_state.disliked, DISLIKED_FILE)
                    new_entry = pd.DataFrame([{
                        'title': rm['title'],
                        'year': rm['year'],
                        'rating': None,
                        'matched_id': rm.get('matched_id', 999999),
                        'genre': rm.get('genre', 'Mixed'),
                        'poster_path': rm.get('poster_path')
                    }])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates(subset=['title'])
                    save_list(st.session_state.watched, WATCHED_FILE)
                    st.session_state.to_watch = st.session_state.to_watch[st.session_state.to_watch['title'] != rm['title']]
                    save_list(st.session_state.to_watch, TO_WATCH_FILE)
                    del st.session_state.random_pick
                    st.rerun()
            with col3:
                if st.button("❌ Cancel", key="random_cancel"):
                    del st.session_state.random_pick
                    st.rerun()
    
    if len(st.session_state.to_watch) > 0:
        cols = st.columns(2)
        for idx, (i, row) in enumerate(st.session_state.to_watch.reset_index(drop=True).iterrows()):
            col = cols[idx % 2]
            with col:
                with st.container():
                    st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #475569;">
                    """, unsafe_allow_html=True)
                    
                    if pd.notna(row.get('poster_path')):
                        st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=140)
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
                with st.container():
                    st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #475569;">
                    """, unsafe_allow_html=True)
                    
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

st.sidebar.caption("✅ Clean & Stable Version")
