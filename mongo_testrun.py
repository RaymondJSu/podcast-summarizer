import certifi
from dotenv import load_dotenv, find_dotenv
import os
from pymongo.mongo_client import MongoClient

load_dotenv(find_dotenv())
PWD = os.environ.get("MONGODB_PWD")

url = f"mongodb+srv://raymondjsu:{PWD}@cluster0.uile4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

cluster = MongoClient(url, tlsCAFile=certifi.where())
db = cluster["sample_mflix"]
collection = db["movies"]

results = collection.find({"title":"The Great Train Robbery"})
for result in results:
    print(result)


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



