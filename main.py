import streamlit as st
from pymongo import MongoClient

def fetch_episodes():
    client = MongoClient('your-mongodb-connection-string')
    db = client.podcast_summarizer
    episodes = db.episodes.find().sort("timestamp", -1)
    return episodes

st.title("Podcast Summarizer")
episodes = fetch_episodes()
for episode in episodes:
    st.header(episode['title'])
    st.subheader(episode['timestamp'])
    st.write(episode['summary'])
