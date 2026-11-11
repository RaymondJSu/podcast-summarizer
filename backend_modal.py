import modal
import feedparser
import requests
import os
import urllib
import tempfile
import hashlib
import uuid
from groq import Groq
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
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
    timeout=600, # 10 minutes timeout for long podcasts
    scaledown_window=2
)
def process_podcast(audio_url):
    """
    Downloads audio to temp storage, transcribes via Groq, 
    and returns the transcript.
    """
    # Use tempfile to ensure the file is deleted automatically after the function ends
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as temp_audio:
        print(f"Downloading audio to temporary storage...")
        with requests.get(audio_url, stream=True, timeout=(10, 60)) as r:
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
            return transcription
        except Exception as e:
            print(f"Transcription error: {e}")
            raise

@app.function(secrets=[modal.Secret.from_name("my-groq-secret")], timeout=300, scaledown_window=2)
def generate_summary(transcript):
    if not transcript:
        raise ValueError("No transcript")

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

        tldr = tldr_response.choices[0].message.content
        summary = summary_response.choices[0].message.content
        if not tldr or not tldr.strip() or not summary or not summary.strip():
            raise ValueError("Empty summary response")
        return tldr, summary
    except Exception as e:
        print(f"Summarization error: {e}")
        raise

def get_mongo_client():
    user = urllib.parse.quote_plus(os.environ["MONGO_USER"])
    pwd = urllib.parse.quote_plus(os.environ["MONGO_PASSWORD"])
    host = os.environ["MONGO_HOST"]
    uri = f"mongodb+srv://{user}:{pwd}@{host}/"
    return MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)

@app.function(secrets=[modal.Secret.from_name("my-mongodb-secret")], timeout=60, scaledown_window=2)
def store_episode_data(episode_id, podcast_feed_url, episode_title, TLDROutput, SummaryOutput, publish_date):
    with get_mongo_client() as client:
        episodes = client.podcast_summarizer.episodes
        episode_data = {
            "feed_url": podcast_feed_url,
            "title": episode_title,
            "publish_date": publish_date,
            "TLDR": TLDROutput,
            "summary": SummaryOutput,
            "timestamp": datetime.datetime.now()
        }

        episodes.update_one({"_id": episode_id}, {"$setOnInsert": episode_data}, upsert=True)
        print(f"Successfully stored in MongoDB: {episode_title}")

@app.function(
    schedule=modal.Cron("*/30 * * * *"),
    secrets=[modal.Secret.from_name("my-mongodb-secret")],
    timeout=1200,
    max_containers=1,
    scaledown_window=2
)
def main(podcast_feed_url = "https://www.spreaker.com/show/5725002/episodes/feed"):
    response = requests.get(podcast_feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    response.raise_for_status()
    podcast_feed = feedparser.parse(response.content)
    if not podcast_feed.entries:
        print("No entries found in RSS feed.")
        return

    # shortcut: only the latest entry is polled; add catch-up if multiple episodes arrive between polls.
    episode = podcast_feed.entries[0]
    audio_url = next((item.get("href") for item in episode.get("enclosures", []) if item.get("href")), None)
    if not audio_url or not episode.get("title") or not episode.get("published"):
        raise ValueError("Episode is missing audio, title, or publish date")
    episode_title, publish_date = episode["title"], episode["published"]
    identity = episode.get("id") or audio_url
    episode_id = hashlib.sha256(f"{podcast_feed_url}\n{identity}".encode()).hexdigest()

    with get_mongo_client() as client:
        db = client.podcast_summarizer
        invalid = [None, "", "No transcript", "Error generating summary"]
        existing = db.episodes.find_one({
            "$or": [
                {"_id": episode_id},
                {"title": episode_title, "publish_date": publish_date, "feed_url": {"$exists": False}}
            ],
            "TLDR": {"$nin": invalid}, "summary": {"$nin": invalid}
        })
        if existing:
            print(f"Already summarized: {episode_title}")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        token = uuid.uuid4().hex
        try:
            # MongoDB's unique _id makes claiming atomic, including overlapping invocations.
            db.episode_jobs.find_one_and_update(
                {"_id": episode_id, "$or": [
                    {"status": "failed"},
                    {"status": "processing", "lease_until": {"$lte": now}}
                ]},
                {"$set": {"status": "processing", "token": token,
                          "lease_until": now + datetime.timedelta(hours=1)}},
                upsert=True
            )
        except DuplicateKeyError:
            print(f"Already claimed: {episode_title}")
            return

        claim = {"_id": episode_id, "token": token}
        try:
            transcript = process_podcast.remote(audio_url)
            TLDROutput, SummaryOutput = generate_summary.remote(transcript)
            store_episode_data.remote(episode_id, podcast_feed_url, episode_title,
                                      TLDROutput, SummaryOutput, publish_date)
            db.episode_jobs.update_one(claim, {"$set": {"status": "completed"}})
        except Exception:
            db.episode_jobs.update_one(claim, {"$set": {"status": "failed"}})
            raise

@app.local_entrypoint()
def test_run(url=None):
    if url:
        main.remote(url)
    else:
        main.remote()
