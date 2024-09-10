import certifi
from dotenv import load_dotenv, find_dotenv
import os
from pymongo.mongo_client import MongoClient
import datetime

load_dotenv(find_dotenv())
PWD = os.environ.get("MONGODB_PWD")

url = f"mongodb+srv://raymondjsu:{PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
title = 'Wall Street Breakfast - Apple unveils AI for new iPhones, watches and AirPods'
summary = 'Apple unveiled new iPhones, Apple watches and AirPods. CEO Tim Cook said the new iPhone 16 is designed for AI from the ground up. Apple Intelligence, its AI platform, will launch in English as a beta in October with iOS 18.1.'
# cluster = MongoClient(url, tlsCAFile=certifi.where())
# db = cluster["sample_mflix"]
# collection = db["movies"]

# results = collection.find({"title":"The Great Train Robbery"})
# for result in results:
#     print(result)

def store_episode_data(url, title, summary):
    client = MongoClient(url, tlsCAFile=certifi.where())
    db = client.podcast
    episodes = db.episodes
    episode_data = {
        "_id": 0,
        "title": title,
        "summary": summary,
        "timestamp": datetime.datetime.now()
    }
    episodes.insert_one(episode_data)

store_episode_data(url, title, summary)
"""
# Create a new client and connect to the server
client = MongoClient(url, tlsCAFile=certifi.where())
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

"""



