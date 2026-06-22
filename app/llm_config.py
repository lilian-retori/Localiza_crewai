import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class SimpleQwenLLM:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
        self.model = os.getenv("OPENAI_MODEL_NAME", "qwen/qwen-2.5-72b-instruct")

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY não encontrada no .env")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def call(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Você é um assistente preciso de automação web."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content