from dotenv import load_dotenv
import os



load_dotenv()
# config = dotenv.dotenv_values(".env")
# openai.api_key = config['OPENAI_API_KEY']
api_key_assemblyai = os.getenv('API_KEY_ASSEMBLYAI')
api_key_listennotes = os.getenv('API_KEY_LISTENNOTES')

print(f"API Key AssemblyAI: {api_key_assemblyai}")
print(f"API Key ListenNotes: {api_key_listennotes}")

