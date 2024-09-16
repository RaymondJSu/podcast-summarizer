import modal
import whisper
import feedparser
import requests
import openai
import os
import urllib
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pathlib import Path
import time

# Modal app setup
app = modal.App(
    image=modal.Image.debian_slim().pip_install(
        "feedparser",
        "openai",
        "requests",
        "openai-whisper",
        "tiktoken",
        "ffmpeg-python",
        "pymongo"
    ).apt_install("ffmpeg"),
    name="podcast_summarizer"
)

# Define a persistent volume to store the Whisper model
volume = modal.Volume.from_name("podcast-storage", create_if_missing=True)

@app.function(volumes={"/podcast-storage": volume})
def download_whisper_model():
    
    # Whisper model download path inside the container
    model_path = "/podcast-storage/base.en"

    # Check if the model is already downloaded to avoid re-downloading
    if not os.path.exists(model_path):
        print("Downloading Whisper model...")
        whisper._download(whisper._MODELS["base.en"], "/podcast-storage/", False)
        volume.commit()
        print("Whisper model downloaded.")
    else:
        print("Whisper model already exists.")

@app.function(volumes={"/podcast-storage": volume})
def get_episode_audio_url(podcast_feed_url):

    print("Downloading podcast episode...")

    podcast_feed = feedparser.parse(requests.get(podcast_feed_url, headers={'User-Agent': 'Mozilla/5.0'}).content)
    episode_title = podcast_feed.entries[0].title
    publish_date = podcast_feed.entries[0].published
    audio_url = podcast_feed.entries[0].links[1].href

    episode_file = f"{episode_title.replace(' ', '_')}.mp3"
    episode_file_path = os.path.join("/podcast-storage", episode_file)

    # Download the podcast episode to the container's volume
    with requests.get(audio_url, stream=True) as r:
        r.raise_for_status()
        with open(episode_file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    volume.commit()
    print(f"Downloaded episode to: {episode_file_path}")
    
    # Check the contents of the directory
    print("Contents of the folder:", os.listdir("/podcast-storage"))

    # Verify the file was downloaded
    if not os.path.exists(episode_file_path):
        print(f"Error: File not found at {episode_file_path}")
        return


    return episode_file_path, episode_title, publish_date



@app.function(volumes={"/podcast-storage": volume}, gpu="any")
def transcribe(audio_file_path):
   
    # Debugging: Print the absolute path
    print(f"Transcribing audio file from path: {audio_file_path}")

    time.sleep(10)

    # Check folder contents for debug
    print("Contents of the folder:", os.listdir("/podcast-storage"))
    
    # Check if file exists
    if not os.path.exists(audio_file_path):
        print(f"Error: File does not exist at {audio_file_path}")
        return False

    # Load the Whisper model
    model = whisper.load_model("base.en")
    try:
        # Run the transcription process
        result = model.transcribe(audio_file_path)
        print("Transcription complete!")
        return result['text']
    
    except Exception as e:
        print(f"An error occurred during transcription: {e}")


@app.function(secrets=[modal.Secret.from_name("my-openai-secret")])
def generate_summary(transcript):

    print("Generating summary...")

    api_key = os.environ["OPENAI_API_KEY"]
    client = openai.Client(api_key=api_key)

    instructPrompt = """
                follow a process that distills the following content into key bullet points, 
                focusing on major news items, economic data, stock market reactions, and any additional insights provided. 
                Here's a basic structure: 
                1. identify the main topics. 
                . Group related information. 
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
    print(TLDROutput)

    return TLDROutput, SummaryOutput

@app.function(secrets=[modal.Secret.from_name("my-mongodb-secret")])
def store_episode_data(episode_title, TLDROutput, SummaryOutput, publish_date):

    user, pwd = map(urllib.parse.quote_plus, (os.environ["MONGO_USER"], os.environ["MONGO_PASSWORD"]))
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
    }

    try:
        episodes.insert_one(episode_data)
        print("Stored episode data in MongoDB")
    except Exception as e:
        print(e)

@app.function(secrets=[modal.Secret.from_name("my-mongodb-secret")])
def ping():

    print("ping...")

    user = urllib.parse.quote_plus(os.environ["MONGO_USER"])
    password = urllib.parse.quote_plus(os.environ["MONGO_PASSWORD"])
    host = urllib.parse.quote_plus(os.environ["MONGO_HOST"])

    uri = "mongodb+srv://%s:%s@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" % (user, password)

    client = MongoClient(uri, server_api=ServerApi("1"))
    try:
        client.admin.command("ping")
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

@app.function(volumes={"/podcast-storage": volume})
@app.schedule(cron="0 9,17 * * *")
def main(podcast_feed_url = "https://www.spreaker.com/show/5725002/episodes/feed"):

    # First, download the Whisper model (if needed)
    download_whisper_model.remote()
    volume.reload()
    
    episode_file_path, episode_title, publish_date = get_episode_audio_url.remote(podcast_feed_url)
    volume.reload()

    transcript = transcribe.remote(episode_file_path)
    if not transcript:
        print("Transcription failed!")
        return
    
    TLDROutput, SummaryOutput = generate_summary.remote(transcript)
    
    store_episode_data.remote(episode_title, TLDROutput, SummaryOutput, publish_date)

    # Delete the audio file
    # if os.path.exists(episode_file_path):
    #     os.remove(episode_file_path)
    #     print(f"Deleted file: {episode_file_path}")
    # else:
    #     print(f"File not found: {episode_file_path}")
