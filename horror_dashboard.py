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
    df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
    horror_style_keywords = "found footage handheld camera supernatural possession demon paranormal ghost haunted exorcism slasher psychological slow burn atmospheric jump scare horror creepy terrifying disturbing"
    df['features'] = df['overview'].fillna('') + ' ' + df['director'].fillna('') + ' ' + df['cast'].fillna('') + ' ' + horror_style_keywords
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()

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
    
    # Safely get director and cast columns (they might not exist)
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
WATCHED_FILE = "watched_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

# ====================== IMPROVED MATCHING WITH YEAR ======================
def smart_match(title, year=None):
    # Get top title matches
    matches = process.extract(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=10)
    
    best_match = None
    best_score = 0
    
    for match_title, score in matches:
        if score < 65:
            continue
        matched_row = horror_df[horror_df['title'] == match_title].iloc[0]
        movie_year = matched_row['year']
        
        # Year bonus
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
                    'matched_id': int(best_row['id'])
                })
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
        if st.button("Clear All", use_container_width=True):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])
            save_watched_list(st.session_state.watched)
            st.rerun()
    else:
        st.info("No movies yet. Import from Letterboxd or add manually.")

with tab2:
    st.header("🎯 Recommendations For You")
    if len(st.session_state.watched) == 0:
        st.warning("Add some watched movies first!")
    else:
        sim = compute_similarity_matrix(horror_df['features'])
        watched_titles = st.session_state.watched['title'].tolist()
        watched_idx = horror_df[horror_df['title'].isin(watched_titles)].index.tolist()
        if len(watched_idx) > 0:
            scores = sim[watched_idx].mean(axis=0)
            recs = horror_df.copy()
            recs['similarity'] = scores
            recs = recs[~recs['title'].isin(watched_titles)]
            recs = recs.sort_values('similarity', ascending=False).head(10)
            for _, row in recs.iterrows():
                with st.container():
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    st.caption(f"Director: {row['director']} • TMDB: {row['vote_average']:.1f}")
                    st.write(str(row['overview'])[:180] + "...")
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        rating = st.selectbox("Rate", [1,2,3,4,5], index=3, key=f"r_{int(row['id'])}", label_visibility="collapsed")
                    with col2:
                        if st.button("✅ Mark as Watched", key=f"w_{int(row['id'])}", use_container_width=True):
                            new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': rating, 'matched_id': int(row['id'])}])
                            st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                            save_watched_list(st.session_state.watched)
                            st.toast(f"Added with {rating} stars!", icon="⭐")
                            st.rerun()
                    st.link_button("🔗 TMDB", f"https://www.themoviedb.org/movie/{int(row['id'])}", use_container_width=True)
                    st.divider()

with tab3:
    st.header("🔍 Check If You've Seen It")
    q = st.text_input("Search movie title")
    if q:
        best_row = smart_match(q)
        if best_row is not None:
            row = best_row
            seen = row['title'] in st.session_state.watched['title'].values
            st.subheader(f"{row['title']} ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
            st.write(row['overview'])
            if seen:
                st.success("✅ You've seen this!")
            else:
                st.warning("❌ Not in your list yet")
                if st.button("Add to Watched", use_container_width=True):
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': int(row['id'])}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.rerun()
        else:
            st.info("Movie not found. Try different spelling.")

st.sidebar.caption("Year-aware matching enabled")
