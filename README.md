# Podcast Summarizer.AI

## Overview

This repository contains the backend for **Podcast Summarizer.Ai**, which processes podcast episodes, transcribes them using OpenAI's Whisper API, generates summaries using ChatGPT, and stores them in MongoDB. The backend is hosted using **Modal**.

## Live Demo

You can view the live project here: [Podcast Summarizer.Ai](https://podcast-summarizer-frontend.onrender.com)

## Features

- Fetch podcast episodes via RSS feed.
- Transcribe podcast audio using OpenAI's Whisper API.
- Generate TLDR and full summaries using OpenAI's ChatGPT.
- Store episode metadata (title, publish date, TLDR, summary) in MongoDB.
- Serve podcast episode summaries via REST API.

### Description 
Fetch all podcast episodes, sorted by publish date (latest first).
### Response 
A list of episodes in JSON format.
  ```json
  [
    {
      "title": "Episode 1",
      "publish_date": "2024-09-13T14:45:01.915+00:00",
      "TLDR": "Brief summary of the episode.",
      "summary": "Detailed summary of the episode."
    },
    
  ]
  ```
## Tech Stack
- Node.js / Express: Backend API framework.
- MongoDB: Database for storing podcast episode summaries.
- Modal: Cloud platform for running server-side processes.
- OpenAI Whisper: Used for podcast audio transcription.
- OpenAI ChatGPT: Used for generating summaries.

### Prereqisites

Environment Variables
Create a `.env` file in the root directory to store sensitive information such as MongoDB connection string and OpenAI API keys. The following environment variables should be included:
```bash
MONGO_URI=<your-mongodb-uri>
OPENAI_API_KEY=<your-openai-api-key>
```
### required library 

- openai
- python-dotenv
- requests
- certify
- feedparser
- git+https://github.com/openai/whisper.git

## Modal Setup and Deployment

### Prerequisites
Ensure you have a Modal account and the necessary credentials.

### Steps to Deploy on Modal
1. Install the Modal CLI on your local machine:

```bash
pip install modal
```
2. Set up your Modal secret on the dashboard

3. Define your Modal functions for tasks like transcribing audio, generating summaries, and storing episode data in MongoDB.

4. Deploy the Modal app using:

```bash
modal deploy
```
5. You can monitor and manage the backend via the Modal dashboard.

### test run the app on modal with local_entrypoint() decorator
```python
@app.local_entrypoint()
def main(rss_feed):
```
and run
```bash
modal run app.py::main
```

## Learning notes from OP
1. Can't fetch the audio file in Modal's Volume

- After diving into Modal documents, I realized that Unlike a networked filesystem, you need to explicitly reload the Volume to see changes made since it was first mounted. 

- Similarly, any volume changes made within a container need to be committed for those the changes to become visible outside the current container.

2. Middleware
3. API handling
4. MongoDB, bad auth

### Mongo DB issues
Should you ran into issues when connecting mongo db with python, try 

```bash
pip install certifi
```

and update 

```python
MongoClient(uri, tlsCAFile=certifi.where())
```
sources: 
1. [MongoDB community](https://www.mongodb.com/community/forums/t/ssl-certificate-verify-failed-certificate-verify-failed-unable-to-get-local-issuer-certificate-ssl-c-997/208879/1)

2. [stack overflow](https://stackoverflow.com/questions/68123923/pymongo-ssl-certificate-verify-failed-certificate-verify-failed-unable-to-ge)