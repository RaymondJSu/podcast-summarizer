import streamlit as st
from pymongo import MongoClient
import os
import certifi

MONGODB_PWD = os.getenv('MONGODB_PWD')
url = f"mongodb+srv://raymondjsu:{MONGODB_PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"


def fetch_episodes():
    client = MongoClient(url, tlsCAFile=certifi.where())
    db = client.podcast_summarizer
    episodes = db.episodes.find().sort("timestamp", -1)
    return episodes

st.title("Podcast Summarizer")
episodes = fetch_episodes()
for episode in episodes:
    st.header(episode['title'])
    st.subheader(episode['timestamp'])
    st.write(episode['summary'])

markdown_string = """

"""

st.markdown(markdown_string)