import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import process, fuzz

st.set_page_config(page_title="Horror Movie Tracker & Recommender", page_icon="👻", layout="wide")

st.title("👻 Horror Movie Dashboard")
st.markdown("Track what you've seen • Get smarter recommendations")

# Load data
@st.cache_data
def load_horror_data():
    df = pd.read_csv("best_horror_movies.csv")
    df = df.dropna(subset=['title', 'overview'])
    df['year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
    df['features'] = (df['overview'].fillna('') + ' ' + 
                      df['director'].fillna('') + ' ' + 
                      df['cast'].fillna(''))
    df = df.reset_index(drop=True)
    return df

horror_df = load_horror_data()

# Similarity matrix
@st.cache_data
def compute_similarity_matrix(features):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf = vectorizer.fit_transform(features)
    return cosine_similarity(tfidf)

# Session state
if 'watched' not in st.session_state:
    st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])

# Sidebar
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
        st.sidebar.success(f"Imported {len(matched)} movies!")

st.sidebar.subheader("➕ Add Manually")
manual_title = st.sidebar.text_input("Movie title")
if st.sidebar.button("Add Movie") and manual_title:
    match = process.extractOne(manual_title, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70:
        matched_row = horror_df[horror_df['title'] == match[0]].iloc[0]
        new_entry = pd.DataFrame([{
            'title': match[0],
            'year': matched_row['year'],
            'rating': None,
            'matched_id': int(matched_row['id'])
        }])
        st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
        st.sidebar.success(f"Added: {match[0]}")

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 My Watched", "🎯 Recommendations", "🔍 Check a Movie"])

with tab1:
    st.header("Your Horror Watch History")
    if len(st.session_state.watched) > 0:
        display_df = st.session_state.watched.merge(
            horror_df[['title', 'vote_average', 'director']], 
            on='title', how='left'
        )
        st.dataframe(display_df[['title', 'year', 'rating', 'vote_average', 'director']], use_container_width=True)
        
        col1, col2 = st.columns(2)
        col1.metric("Movies Seen", len(st.session_state.watched))
        if st.session_state.watched['rating'].notna().any():
            col2.metric("Avg Rating", f"{st.session_state.watched['rating'].mean():.1f}")
        
        if st.button("Clear All"):
            st.session_state.watched = pd.DataFrame(columns=['title', 'year', 'rating', 'matched_id'])
            st.rerun()
    else:
        st.info("No movies yet. Import or add some above.")

with tab2:
    st.header("🎯 Personalized Recommendations")
    if len(st.session_state.watched) == 0:
        st.warning("Add some movies first!")
    else:
        sim_matrix = compute_similarity_matrix(horror_df['features'])
        watched_titles = st.session_state.watched['title'].tolist()
        watched_idx = horror_df[horror_df['title'].isin(watched_titles)].index.tolist()
        
        if len(watched_idx) > 0:
            scores = sim_matrix[watched_idx].mean(axis=0)
            recs = horror_df.copy()
            recs['similarity'] = scores
            recs = recs[~recs['title'].isin(watched_titles)]
            recs = recs.sort_values('similarity', ascending=False).head(12)
            
            for _, row in recs.iterrows():
                cols = st.columns([4, 1.4, 1.6])
                with cols[0]:
                    st.markdown(f"**{row['title']}** ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
                    st.caption(f"Director: {row['director']} • Score: {row['vote_average']:.1f}")
                    st.write(str(row['overview'])[:200] + "...")
                with cols[1]:
                    st.metric("Relevance", f"{row['similarity']:.2f}")
                with cols[2]:
                    st.link_button("TMDB", f"https://www.themoviedb.org/movie/{int(row['id'])}")
                    if st.button("✅ I've seen this", key=f"btn_{row['id']}"):
                        new_row = pd.DataFrame([{
                            'title': row['title'],
                            'year': row['year'],
                            'rating': None,
                            'matched_id': int(row['id'])
                        }])
                        st.session_state.watched = pd.concat([st.session_state.watched, new_row]).drop_duplicates()
                        st.toast("Added! Recommendations updated.", icon="👻")
                        st.rerun()
                st.divider()

with tab3:
    st.header("🔍 Check a Movie")
    query = st.text_input("Search movie title")
    if query:
        match = process.extractOne(query, horror_df['title'].tolist(), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 70:
            row = horror_df[horror_df['title'] == match[0]].iloc[0]
            seen = match[0] in st.session_state.watched['title'].values
            st.subheader(f"{match[0]} ({int(row['year']) if pd.notna(row['year']) else 'N/A'})")
            st.write(row['overview'])
            if seen:
                st.success("✅ You have seen this")
            else:
                st.warning("❌ Not seen yet")
                if st.button("Mark as Seen"):
                    new_entry = pd.DataFrame([{'title': match[0], 'year': row['year'], 'rating': None, 'matched_id': int(row['id'])}])
                    st.session_state.watched = pd.concat([st.session_state.watched, new_entry]).drop_duplicates()
                    st.rerun()
        else:
            st.info("Movie not found.")

st.sidebar.caption("Made for Zach 👻")
