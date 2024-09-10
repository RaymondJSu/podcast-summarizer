from pathlib import Path
import requests
# import openai
# import whisper
from dotenv import load_dotenv
import os
import json

load_dotenv()

X_ListenAPI_Key = os.getenv('X_ListenAPI_Key')
listennotes_episode_endpoint = 'https://listen-api.listennotes.com/api/v2/episodes'
headers_listennotes = {
  'X-ListenAPI-Key': X_ListenAPI_Key,
}
WSB_id = 'f59182551ad149b693d7856390ea6f7a'
episode_id = 'f399406330bb4d82972c1f5743480993'

def get_episode_audio_url(episode_id):
    url = listennotes_episode_endpoint + '/' + episode_id
    response = requests.request('GET', url, headers=headers_listennotes)

    data = response.json()

    episode_title = data['title']
    thumbnail = data['thumbnail']
    podcast_title = data['podcast']['title']
    audio_url = data['audio']

    return audio_url, thumbnail, podcast_title, episode_title

def main():
    audio_url, thumbnail, podcast_title, episode_title = get_episode_audio_url(episode_id)
    filename = "podcast_episode.mp3"
    folder_path = "./podcast"

    # Create the podcast folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_path = os.path.join(folder_path, filename)

    # Download the podcast episode as mp3
    response = requests.get(audio_url, stream=True)
    with open(file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                file.write(chunk)

# will need to rewrite to def save_transcript(episode_id):
if __name__ == '__main__':
    main()







"""

def get_transcribe_podcast(rss_url, local_path):
    print ("Starting Podcast Transcription Function")
    print ("Feed URL: ", rss_url)
    print ("Local Path:", local_path)

    # Read from the RSS Feed URL

    intelligence_feed = feedparser.parse(rss_url)
    for item in intelligence_feed.entries[0].links:
        if (item['type'] == 'audio/mpeg'):
            episode_url = item.href
    episode_name = "podcast_episode.mp3"
    print ("RSS URL read and episode URL: ", episode_url)

    # Download the podcast episode by parsing the RSS feed

    p = Path(local_path)
    p.mkdir(exist_ok=True)

    print ("Downloading the podcast episode")

    with requests.get(episode_url, stream=True) as r:
        r.raise_for_status()
        episode_path = p.joinpath(episode_name)
    with open(episode_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

"""
