import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import process, fuzz
import os

st.set_page_config(page_title="Horror Movie Tracker & Recommender", page_icon="👻", layout="wide")
st.title("👻 Horror Movie Dashboard")
st.markdown("Track what you've seen • Get smarter recommendations")

# ====================== LOAD DATA ======================
@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['title', 'overview'])
    df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
    df['features'] = (df['overview'].fillna('') + ' ' + df['director'].fillna('') + ' ' + df['cast'].fillna(''))
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()
@st.cache_data
def compute_similarity_matrix(features):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf = vectorizer.fit_transform(features)
    return cosine_similarity(tfidf)
# ====================== PERSISTENT WATCHED LIST ======================
WATCHED_FILE = "watched_list.csv"

def load_watched_list():
    if os.path.exists(WATCHED_FILE):
        return pd.read_csv(WATCHED_FILE)
    else:
        return pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

def save_watched_list(df):
    df.to_csv(WATCHED_FILE, index=False)

if 'watched' not in st.session_state:
    st.session_state.watched = load_watched_list()

# ====================== SIDEBAR ======================
st.sidebar.header("📥 Import Watched Movies")
uploaded = st.sidebar.file_uploader("Upload Letterboxd diary.csv", type="csv")

if uploaded:
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
        match = process.extractOne(title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 75:
            matched_row = horror_df[horror_df['title'] == match[0]].iloc[0]
            matched.append({
                'title': match[0],
                'year': matched_row['year'],
                'rating': row.get('rating'),
                'matched_id': int(matched_row['id'])
            })
    if matched:
        new_df = pd.DataFrame(matched)
        st.session_state.watched = pd.concat([st.session_state.watched, new_df]).drop_duplicates(subset=['title'])
        save_watched_list(st.session_state.watched)
        st.sidebar.success(f"Imported {len(matched)} movies!")

st.sidebar.subheader("➕ Add Manually")
manual = st.sidebar.text_input("Movie title")
if st.sidebar.button("Add") and manual:
    match = process.extractOne(manual, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70:
        matched_row = horror_df[horror_df['title'] == match[0]].iloc[0]
        new_entry = pd.DataFrame([{'title': match[0], 'year': matched_row['year'], 'rating': None, 'matched_id': int(matched_row['id'])}])
        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
        save_watched_list(st.session_state.watched)
        st.sidebar.success(f"Added: {match[0]}")

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 My Watched", "🎯 Recommendations", "🔍 Check a Movie"])

with tab1:
    st.header("Your Horror Watch History")
    if len(st.session_state.watched) > 0:
        display = st.session_state.watched.merge(horror_df[['title', 'vote_average', 'director']], on='title', how='left')
        st.dataframe(display[['title', 'year', 'rating', 'vote_average', 'director']], use_container_width=True)
        c1, c2 = st.columns(2)
        c1.metric("Movies Seen", len(st.session_state.watched))
        if st.session_state.watched['rating'].notna().any():
            c2.metric("Avg Your Rating", f"{st.session_state.watched['rating'].mean():.1f}")
        if st.button("Clear All"):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])
            save_watched_list(st.session_state.watched)
            st.rerun()
    else:
        st.info("No movies yet. Import or add some in the sidebar")

with tab2:
    st.header("🎯 Personalized Recommendations")
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
            recs = recs.sort_values('similarity', ascending=False).head(12)
            
            for _, row in recs.iterrows():
                cols = st.columns([4, 1.4, 1.6])
                with cols[0]:
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    st.caption(f"Director: {row['director']} • TMDB: {row['vote_average']:.1f}/10")
                    st.write(str(row['overview'])[:200] + "...")
                with cols[1]:
                    st.metric("Relevance", f"{row['similarity']:.2f}")
                with cols[2]:
                    st.link_button("🔗 TMDB", f"https://www.themoviedb.org/movie/{int(row['id'])}")
                    
                    # === CLEAN SINGLE BUTTON ===
                    rating = st.selectbox(
                        "Rate this movie", 
                        options=[1, 2, 3, 4, 5], 
                        index=3, 
                        key=f"rate_{int(row['id'])}"
                    )
                    if st.button("✅ Mark as Watched", key=f"watch_{int(row['id'])}"):
                        new_entry = pd.DataFrame([{
                            'title': row['title'],
                            'year': row['year'],
                            'rating': rating,
                            'matched_id': int(row['id'])
                        }])
                        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                        save_watched_list(st.session_state.watched)
                        st.toast(f"Added with {rating} stars! It will now appear in My Watched.", icon="⭐")
                        st.rerun()
                st.divider()
with tab3:
    st.header("🔍 Check a Movie")
    q = st.text_input("Movie title")
    if q:
        match = process.extractOne(q, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 70:
            row = horror_df[horror_df['title'] == match[0]].iloc[0]
            seen = match[0] in st.session_state.watched['title'].values
            st.subheader(f"{match[0]} ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
            st.write(row['overview'])
            if seen:
                st.success("✅ You've seen this!")
            else:
                st.warning("❌ Not in your list")
                if st.button("Add to Watched"):
                    new_entry = pd.DataFrame([{'title': match[0], 'year': row['year'], 'rating': None, 'matched_id': int(row['id'])}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    save_watched_list(st.session_state.watched)
                    st.rerun()
        else:
            st.info("Movie not found in database.")

st.sidebar.caption("Watched list now saves automatically ⭐")
