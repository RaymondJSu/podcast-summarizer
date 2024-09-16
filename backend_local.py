import requests
import feedparser
import openai
import whisper
from openai import OpenAI
from dotenv import load_dotenv
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import datetime
import certifi
from pathlib import Path

load_dotenv()

MONGODB_PWD = os.getenv('MONGODB_PWD')
mongoDB_uri = f"mongodb+srv://raymondjsu:{MONGODB_PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
API_KEY_chatGPT = os.getenv('API_KEY_chatGPT')

client = OpenAI(
    api_key=API_KEY_chatGPT,
)

podcast_feed_url = "https://www.spreaker.com/show/5725002/episodes/feed"


def get_episode_audio_url(podcast_feed_url):

    podcast_feed = feedparser.parse(requests.get(podcast_feed_url, headers={'User-Agent': 'Mozilla/5.0'}).content)
    episode_title = podcast_feed.entries[0].title
    publish_date = podcast_feed.entries[0].published
    audio_url = podcast_feed.entries[0].links[1].href

    return audio_url, episode_title, publish_date

def transcribe(audio_data):

    print("Transcribing podcast episode...")

    model = whisper.load_model("base.en")
    transcript = model.transcribe(audio_data, fp16=False)

    print("Transcription complete!")

    return transcript["text"]

def generate_summary(transcript):

    print("Generating summary...")

    instructPrompt = """
follow a process that distills the following content into key bullet points, focusing on major news items, economic data, stock market reactions, and any additional insights provided. 
Here's a basic structure: 
1. identify the main topics. 
2. Group related information. 
3. highlight key numbers and reactions. 
4. condense for clarity. 
5. maintain a logical flow. 

Now please create a brief yet comprehensive summary that conveys the essential information:
"""
    TLDRPrompt = """
please provide a TLDR version of the following transcript, 
please limit to 30 to 60 words, or about 1-3 sentences. 
The goal is to provide a quick, high-level overview that captures the essence of the content. 

Here's the transcript:
"""

    prompt = TLDRPrompt + transcript
    TLDROutput = client.chat.completions.create(model="gpt-3.5-turbo",
                                            messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                    {"role": "user", "content": prompt}
                                                    ]
                                            )
    prompt = instructPrompt + transcript
    SummaryOutput = client.chat.completions.create(model="gpt-3.5-turbo",
                                            messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                    {"role": "user", "content": prompt}
                                                    ]
                                            )
    TLDROutput = TLDROutput.choices[0].message.content
    SummaryOutput = SummaryOutput.choices[0].message.content

    print("Summary complete!")

    return TLDROutput, SummaryOutput

def store_episode_data(uri, title,TLDROutput, SummaryOutput, publish_date):
    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client.podcast_summarizer
    episodes = db.episodes
    episode_data = {
        "title": title,
        "publish_date": publish_date,
        "TLDR": TLDROutput,
        "summary": SummaryOutput,
        "timestamp": datetime.datetime.now()
    }
    episodes.insert_one(episode_data)
    print("Stored episode data in MongoDB")

def ping():

    mongoDB_uri = f"mongodb+srv://raymondjsu:{MONGODB_PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

    client = MongoClient(mongoDB_uri, server_api=ServerApi("1"))
    try:
        client.admin.command("ping")
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

def main():
    print("Downloading podcast episode...")
    episode_url, episode_title, publish_date = get_episode_audio_url(podcast_feed_url)
    episode_file = f"{episode_title.replace(' ', '_')}.mp3"
    folder_path = os.path.abspath("./podcast/")

    # Create the podcast folder if it doesn't exist
    Path(folder_path).mkdir(parents=True, exist_ok=True)
    # Absolute path for the downloaded file
    episode_path = os.path.join(folder_path, episode_file)

    # # Download the podcast episode as mp3
    with requests.get(episode_url, stream=True) as r:
        r.raise_for_status()
        with open(episode_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    print(f"Downloaded episode to: {episode_path}")
    
    transcript = transcribe(episode_path)
    TLDROutput, SummaryOutput = generate_summary(transcript)
    store_episode_data(mongoDB_uri, episode_title, TLDROutput, SummaryOutput, publish_date)
    
    # Delete the audio file
    if os.path.exists(episode_path):
        os.remove(episode_path)
        print(f"Deleted file: {episode_path}")
    else:
        print(f"File not found: {episode_path}")

if __name__ == '__main__':
    main()
    