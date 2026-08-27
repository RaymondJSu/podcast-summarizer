import modal
import feedparser
import requests
import os
import urllib
import tempfile
from groq import Groq
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pathlib import Path
import datetime

# Modal app setup
# We no longer need a Volume because we use Groq for transcription!
app = modal.App(
    image=modal.Image.debian_slim().pip_install(
        "feedparser",
        "groq",
        "requests",
        "pymongo"
    ),
    name="podcast_summarizer"
)

@app.function(
    secrets=[
        modal.Secret.from_name("my-groq-secret"),
    ],
    timeout=600 # 10 minutes timeout for long podcasts
)
def process_podcast(podcast_feed_url):
    """
    Downloads audio to temp storage, transcribes via Groq, 
    and returns transcript + metadata.
    """
    print("Fetching podcast feed...")
    podcast_feed = feedparser.parse(requests.get(podcast_feed_url, headers={'User-Agent': 'Mozilla/5.0'}).content)
    
    if not podcast_feed.entries:
        print("No entries found in RSS feed.")
        return None

    episode_title = podcast_feed.entries[0].title
    publish_date = podcast_feed.entries[0].published
    audio_url = podcast_feed.entries[0].links[1].href

    print(f"Processing episode: {episode_title}")
    
    # Use tempfile to ensure the file is deleted automatically after the function ends
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as temp_audio:
        print(f"Downloading audio to temporary storage...")
        with requests.get(audio_url, stream=True) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                temp_audio.write(chunk)
        
        temp_audio.flush() # Ensure all data is written
        
        # Transcribe via Groq
        print(f"Transcribing via Groq (Whisper Large V3 Turbo)...")
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        
        try:
            with open(temp_audio.name, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(temp_audio.name), file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="text",
                )
            print("Transcription complete!")
            return transcription, episode_title, publish_date
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

@app.function(secrets=[modal.Secret.from_name("my-groq-secret")])
def generate_summary(transcript):
    if not transcript:
        return "No transcript", "No transcript"

    print("Generating summary via Groq GPT OSS 20B...")
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    instructPrompt = """
        follow a process that distills the following content into key bullet points, 
        focusing on major news items, economic data, stock market reactions, and any additional insights provided. 
        Here's a basic structure:

        1. identify the main topics. 
        2. Group related information. 
        3. highlight key numbers and reactions. 
        4. condense for clarity. 
        5. maintain a logical flow. 

        Now please create a brief yet comprehensive summary that conveys the essential information:
    """
    
    TLDRPrompt = """
        Please provide a TLDR version of the following transcript, 
        Please limit to 30 to 60 words, or about 1-3 sentences. 
        The goal is to provide a quick, high-level overview that captures the essence of the content. 

        Here's the transcript:
    """

    model_name = "openai/gpt-oss-20b"

    try:
        # Generate TLDR
        tldr_response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a professional podcast summarizer. You can only generate a TLDR version of the transcript. Now return the TLDR follow this format: TLDR: <TLDR>"},
                {"role": "user", "content": f"{TLDRPrompt}\n\nTranscript: {transcript}"}
            ]
        )
        
        # Generate Full Summary
        summary_response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a professional podcast summarizer."},
                {"role": "user", "content": f"{instructPrompt}\n\nTranscript: {transcript}"}
            ]
        )

        return tldr_response.choices[0].message.content, summary_response.choices[0].message.content
    except Exception as e:
        print(f"Summarization error: {e}")
        return "Error generating summary", "Error generating summary"

@app.function(secrets=[modal.Secret.from_name("my-mongodb-secret")])
def store_episode_data(episode_title, TLDROutput, SummaryOutput, publish_date):
    try:
        user = urllib.parse.quote_plus(os.environ["MONGO_USER"])
        pwd = urllib.parse.quote_plus(os.environ["MONGO_PASSWORD"])
        host = os.environ["MONGO_HOST"]

        uri = f"mongodb+srv://{user}:{pwd}@{host}/"
        client = MongoClient(uri, server_api=ServerApi("1"))

        db = client.podcast_summarizer
        episodes = db.episodes
        episode_data = {
            "title": episode_title,
            "publish_date": publish_date,
            "TLDR": TLDROutput,
            "summary": SummaryOutput,
            "timestamp": datetime.datetime.now()
        }

        episodes.insert_one(episode_data)
        print(f"Successfully stored in MongoDB: {episode_title}")
    except Exception as e:
        print(f"MongoDB Error: {e}")

@app.function(schedule=modal.Cron("0 13,23 * * 1-5"))
def main(podcast_feed_url = "https://www.spreaker.com/show/5725002/episodes/feed"):
    # Step 1: Download & Transcribe (Automatic cleanup via tempfile)
    result = process_podcast.remote(podcast_feed_url)
    if not result:
        return
    transcript, episode_title, publish_date = result

    # Step 2: Summarize
    TLDROutput, SummaryOutput = generate_summary.remote(transcript)
    
    # Step 3: Store
    store_episode_data.remote(episode_title, TLDROutput, SummaryOutput, publish_date)

@app.local_entrypoint()
def test_run(url=None):
    if url:
        main.remote(url)
    else:
        main.remote()
