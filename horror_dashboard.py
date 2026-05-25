import streamlit as st
import pandas as pd
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
    
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()

WATCHED_FILE = "watched_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

# ====================== IMPROVED SMART MATCHING ======================
def smart_match(title, year=None):
    matches = process.extract(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=15)
    best_match = None
    best_score = 0
    
    for match_title, score in matches:
        if score < 68:   # stricter base threshold
            continue
            
        matched_row = horror_df[horror_df['title'] == match_title].iloc[0]
        movie_year = matched_row.get('year')
        
        # Substring penalty (prevents "Alien" matching when you type "Aliens")
        penalty = 0
        if title.lower() in match_title.lower() or match_title.lower() in title.lower():
            if len(title) != len(match_title):   # only penalize if lengths differ
                penalty = 12
        
        # Year bonus
        year_bonus = 0
        if year and pd.notna(movie_year):
            year_diff = abs(int(year) - int(movie_year))
            if year_diff == 0:
                year_bonus = 30
            elif year_diff <= 1:
                year_bonus = 20
            elif year_diff <= 3:
                year_bonus = 12
        
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
if st.sidebar.button("Add", width='stretch') and manual:
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
        cols_to_show = ['title']
        if 'vote_average' in horror_df.columns: cols_to_show.append('vote_average')
        if 'director' in horror_df.columns: cols_to_show.append('director')
        display = st.session_state.watched.merge(horror_df[cols_to_show], on='title', how='left')
        final_cols = [c for c in ['title', 'year', 'rating', 'vote_average', 'director'] if c in display.columns]
        st.dataframe(display[final_cols], width='stretch', height=400)
        col1, col2 = st.columns(2)
        col1.metric("Total Seen", len(st.session_state.watched))
        if st.session_state.watched['rating'].notna().any():
            col2.metric("Avg Rating", f"{st.session_state.watched['rating'].mean():.1f} ⭐")
        if st.button("Clear All", width='stretch'):
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
        watched_titles = st.session_state.watched['title'].tolist()
        recs = horror_df[~horror_df['title'].isin(watched_titles)].copy()
        
        if 'vote_average' in recs.columns:
            recs = recs.sort_values('vote_average', ascending=False)
        else:
            recs = recs.sample(12, random_state=42)
        
        recs = recs.head(12)
        
        for _, row in recs.iterrows():
            with st.container():
                if 'poster_path' in row and pd.notna(row.get('poster_path')):
                    st.image(f"https://image.tmdb.org/t/p/w200{row['poster_path']}", width=140)
                
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                
                # Show all ratings
                rating_text = f"TMDB: {row.get('vote_average', 'N/A'):.1f}"
                if 'imdb_rating' in row and pd.notna(row['imdb_rating']):
                    rating_text += f" | IMDb: {row['imdb_rating']:.1f}"
                elif 'imdb_score' in row and pd.notna(row['imdb_score']):
                    rating_text += f" | IMDb: {row['imdb_score']:.1f}"
                if 'rotten_tomatoes' in row and pd.notna(row['rotten_tomatoes']):
                    rating_text += f" | RT: {row['rotten_tomatoes']}%"
                elif 'tomatometer' in row and pd.notna(row['tomatometer']):
                    rating_text += f" | RT: {row['tomatometer']}%"
                
                st.caption(rating_text)
                st.write(str(row['overview'])[:160] + "..." if len(str(row['overview'])) > 160 else row['overview'])
                
                if st.button("✅ Mark as Watched", key=f"w_{int(row['id'])}", width='stretch'):
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': int(row['id'])}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.toast(f"Added {row['title']}!", icon="⭐")
                    st.rerun()
                
                st.link_button("🔗 TMDB", f"https://www.themoviedb.org/movie/{int(row['id'])}", width='stretch')
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
                if st.button("Add to Watched", width='stretch'):
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': int(row['id'])}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.rerun()
        else:
            st.info("Movie not found. Try different spelling.")

st.sidebar.caption("IMDb + Rotten Tomatoes added")
