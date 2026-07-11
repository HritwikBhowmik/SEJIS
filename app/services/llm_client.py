
import httpx
import os
import re
from fastapi import HTTPException, status
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

NVIDIA_URL = os.getenv("HF_API_URL")
NVIDIA_API_KEY = os.getenv("HF_API_KEY")
LLM_MODEL = os.getenv("HF_LLM_MODEL")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MM = os.getenv("GEMINI_MM")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

async def generate_llm_response(system_prompt: str, chat_history: list) -> str:
    async with httpx.AsyncClient() as client:
        
        # Structure the foundational conversation context matrix
        formatted_messages = [{"role": "system", "content": system_prompt}]
        if len(chat_history) == 0:
            formatted_messages.append({"role": "user", "content": "I'm ready. Please be fair with me."})
        else:
            # Extends the existing {"role": "user"/"assistant", "content": "..."} elements cleanly
            formatted_messages.extend(chat_history)

        # Match Nvidia's target structural payload constraints
        payload = {
            "model": f"{LLM_MODEL}",
            "messages": formatted_messages,
            "max_tokens": 4096,
            "temperature": 1.00,
            "top_p": 0.95,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True}
        }

        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Non-blocking post execution trip
        try:
            nv_response = await client.post(
                NVIDIA_URL,
                headers=headers,
                json=payload,
                timeout=60.0
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to communicate with Nvidia infrastructure: {str(exc)}"
            )

        # Guard assertion matching proper API resolution paths
        if nv_response.status_code != 200:
            print(f"Nvidia Engine Error Output: {nv_response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail="Nvidia model generation pipeline execution failure."
            )
            
        raw_content = nv_response.json()["choices"][0]["message"]["content"]
        
        # Strip out thinking block boundaries (<think>...</think>)
        # This keeps the final evaluation text clean for strict JSON or text processing blocks
        cleaned_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
        
        return cleaned_content
    

async def generate_mm_response(pil_image, system_instruction:str):
    """ Get response from google's multimodal model """
    response = ai_client.models.generate_content(
        model=str(GEMINI_MM),
        contents=[pil_image, system_instruction],
        # Enforce structured JSON schemas directly at the model tier
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        ),
    )

    return response.text

