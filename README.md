# podcast-summarizer
transcribe podcast audio, extract key bullet point, and generate summarize for you!


### run the app
```
modal run app.py::main
```

#### Mongo DB issues
Should you ran into issues when connecting mongo db with python, try 
```
pip install certifi
```
and update 
```
MongoClient(url, tlsCAFile=certifi.where())
```
[MongoDB community](https://www.mongodb.com/community/forums/t/ssl-certificate-verify-failed-certificate-verify-failed-unable-to-get-local-issuer-certificate-ssl-c-997/208879/1)

[stack overflow](https://stackoverflow.com/questions/68123923/pymongo-ssl-certificate-verify-failed-certificate-verify-failed-unable-to-ge)