import streamlit as st
import pandas as pd
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker", page_icon="👻", layout="centered")
st.title("👻 Horror Dashboard")

@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['movie_title', 'movie_info'])
    
    df = df.rename(columns={
        'movie_title': 'title',
        'movie_info': 'overview',
        'directors': 'director',
        'actors': 'cast',
        'original_release_date': 'release_date'
    })
    
    df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
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

def smart_match(title, year=None):
    matches = process.extract(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio, limit=15)
    best_match = None
    best_score = 0
    for match_title, score in matches:
        if score < 68:
            continue
        matched_row = horror_df[horror_df['title'] == match_title].iloc[0]
        movie_year = matched_row.get('year')
        
        penalty = 0
        if "alien" in title.lower() and ("3" in match_title.lower() or "iii" in match_title.lower()):
            penalty = 40
        if "alien" in title.lower() and "2" in match_title.lower():
            penalty = 20
        
        year_bonus = 0
        if year and pd.notna(movie_year):
            year_diff = abs(int(year) - int(movie_year))
            if year_diff == 0:
                year_bonus = 35
            elif year_diff <= 1:
                year_bonus = 22
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
                    'matched_id': best_row.name
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
        new_entry = pd.DataFrame([{'title': best_row['title'], 'year': best_row['year'], 'rating': None, 'matched_id': best_row.name}])
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
        display = st.session_state.watched.merge(horror_df[['title', 'year']], on='title', how='left')
        st.dataframe(display, width='stretch', height=400)
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
                st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                
                rating_text = f"RT: {row.get('tomatometer_rating', 'N/A')}%"
                if 'audience_rating' in row and pd.notna(row['audience_rating']):
                    rating_text += f" | Audience: {row['audience_rating']}%"
                
                st.caption(rating_text)
                st.write(str(row['overview'])[:180] + "..." if len(str(row['overview'])) > 180 else row['overview'])
                
                if st.button("✅ Mark as Watched", key=f"w_{idx}", width='stretch'):
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': idx}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.toast(f"Added {row['title']}!", icon="⭐")
                    st.rerun()
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
                    new_entry = pd.DataFrame([{'title': row['title'], 'year': row['year'], 'rating': None, 'matched_id': row.name}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.rerun()
        else:
            st.info("Movie not found. Try different spelling.")

st.sidebar.caption("Rotten Tomatoes dataset • No posters in this file")
