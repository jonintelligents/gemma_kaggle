from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client()

response = client.models.generate_content(
    model="gemma-3n-e4b-it", contents="Explain how AI works in a few words"
)
print(response.text)