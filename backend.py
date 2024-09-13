import requests
import feedparser
import openai
import whisper
from openai import OpenAI
from dotenv import load_dotenv
import os
from pymongo.mongo_client import MongoClient
import datetime
import certifi

load_dotenv()

X_ListenAPI_Key = os.getenv('X_ListenAPI_Key')
MONGODB_PWD = os.getenv('MONGODB_PWD')
mongoDB_url = f"mongodb+srv://raymondjsu:{MONGODB_PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
API_KEY_chatGPT = os.getenv('API_KEY_chatGPT')

client = OpenAI(
    api_key=API_KEY_chatGPT,
)

podcast_feed_url = "https://www.spreaker.com/show/5725002/episodes/feed"
# listennotes_episode_endpoint = 'https://listen-api.listennotes.com/api/v2/episodes'
# headers_listennotes = {
#   'X-ListenAPI-Key': X_ListenAPI_Key,
# }
# WSB_id = 'f59182551ad149b693d7856390ea6f7a'
# episode_id = 'f399406330bb4d82972c1f5743480993'


def get_episode_audio_url(podcast_feed_url):
    # url = listennotes_episode_endpoint + '/' + episode_id
    # response = requests.request('GET', url, headers=headers_listennotes)

    # data = response.json()

    # episode_title = data['title']
    # thumbnail = data['thumbnail']
    # podcast_title = data['podcast']['title']
    # audio_url = data['audio']
    podcast_feed = feedparser.parse(requests.get(podcast_feed_url, headers={'User-Agent': 'Mozilla/5.0'}).content)
    episode_title = podcast_feed.entries[0].title
    publish_date = podcast_feed.entries[0].published
    audio_url = podcast_feed.entries[0].links[1].href

    return audio_url, episode_title, publish_date

def transcribe(audio_data):
    model = whisper.load_model("base.en")
    transcript = model.transcribe(audio_data)

    return transcript["text"]

def generate_summary(transcript):
    instructPrompt = """
                follow a process that distills the following content into key bullet points, focusing on major news items, economic data, stock market reactions, and any additional insights provided. Here's a basic structure: 1. identify the main topics. 2. Group related information. 3. highlight key numbers and reactions. 4. condense for clarity. 5. maintain a logical flow. Now please create a brief yet comprehensive summary that conveys the essential information:
"""
    TLDRPrompt = """
 please provide a TLDR version of the following transcript, please limit to 30 to 60 words, or about 1-3 sentences. The goal is to provide a quick, high-level overview that captures the essence of the content. Here's the transcript:
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

    return TLDROutput, SummaryOutput

def store_episode_data(url, title,TLDROutput, SummaryOutput, publish_date):
    client = MongoClient(url, tlsCAFile=certifi.where())
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

def main():
    print("Downloading podcast episode...")
    audio_url, episode_title, publish_date = get_episode_audio_url(podcast_feed_url)
    filename = f"{episode_title}.mp3"
    folder_path = "./podcast"

    # Create the podcast folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_path = os.path.join(folder_path, filename)

    # Download the podcast episode as mp3
    # response = requests.get(audio_url, stream=True)
    # with open(file_path, 'wb') as file:
    #     for chunk in response.iter_content(chunk_size=1024):
    #         if chunk:
    #             file.write(chunk)
    print("Downloade complete!")

    print("Transcribing podcast episode...")
    transcript = transcribe(file_path)
    print("Transcription complete!")
    print("Generating summary...")
    TLDROutput, SummaryOutput = generate_summary(transcript)
    print("Summary complete!")
    store_episode_data(mongoDB_url, episode_title, TLDROutput, SummaryOutput, publish_date)
    # Delete the audio file
    # if os.path.exists(file_path):
    #     os.remove(file_path)
    #     print(f"Deleted file: {file_path}")
    # else:
    #     print(f"File not found: {file_path}")

# will need to rewrite to def save_transcript(episode_id):
if __name__ == '__main__':
    main()
