
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is missing from .env")

client = genai.Client(api_key=api_key)

print("\nModels supporting text generation:\n")

for model in client.models.list():
    actions = getattr(model, "supported_actions", []) or []
    if "generateContent" in actions:
        print(model.name)
