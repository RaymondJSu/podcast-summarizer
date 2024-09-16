import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi

MONGO_USER = st.secrets["MONGO_USER"]
MONGO_PWD = st.secrets["MONGODB_PWD"]
print(MONGO_USER, MONGO_PWD)

uri = f"mongodb+srv://{MONGO_USER}:{MONGO_PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    
client = MongoClient(uri, server_api=ServerApi("1"))
db = client.podcast_summarizer
episodes = db.episodes

# Streamlit App
st.set_page_config(page_title="News Digest ", layout="wide")

st.title("Podcast Summarizer")

# Fetch episode data from MongoDB
episode_data = list(episodes.find().sort("publish_date", -1))


# CSS for centering and responsive design
st.markdown("""
    <style>
        body {
            background-color: white;
            color: black;
        }
        .container {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        .episode {
            max-width: 800px;
            width: 100%;
            padding: 15px;
            background-color: white;
            color: black;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        .centered-content {
            text-align: center;
        }
        @media (max-width: 768px) {
            .episode {
                padding: 10px;
            }
        }
    </style>
""", unsafe_allow_html=True)


# Main layout
st.markdown('<div class="container">', unsafe_allow_html=True)


for episode in episode_data:
    title = episode["title"]
    publish_date = episode["publish_date"][:-5]
    TLDR = episode["TLDR"]
    summary = episode["summary"]


    # Display episode information
    st.markdown(f'<div class="episode centered-content">', unsafe_allow_html=True)
    
    st.markdown(f'<h1>{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p>Published on: {publish_date}</p>', unsafe_allow_html=True)
    st.markdown(f'<p>{TLDR}</p>', unsafe_allow_html=True)  # Display TLDR as short summary
    
    st.markdown('<div style="text-align: left;">', unsafe_allow_html=True)
    with st.expander("Read More"):
        st.markdown(f'<p>{summary}</p>', unsafe_allow_html=True)  # Full summary shown when expanded
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)


st.markdown('</div>', unsafe_allow_html=True)