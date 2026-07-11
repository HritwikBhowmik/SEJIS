
import httpx
import os
import re
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL")

NVIDIA_URL = os.getenv("HF_API_URL")
NVIDIA_API_KEY = os.getenv("HF_API_KEY")
NVIDIA_LLM_MODEL = os.getenv("HF_LLM_MODEL")

async def extract_jobrole_pdf(raw_pdf_text:str):
    
    stage1_prompt = (
        "Extract only the key technical skills, programming languages, framework tools, "
        "and years of experience from this raw resume text. Avoid prose. Be concise.\n\n"
        f"Resume Text:\n{raw_pdf_text}"
    )
    
    async with httpx.AsyncClient() as client:
        groq_response = await client.post(
            str(GROQ_API_URL),
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_LLM_MODEL,
                "messages": [{"role": "user", "content": stage1_prompt}],
                "temperature": 0.1
            },
            timeout=30.0
        )
        
        if groq_response.status_code != 200:
            print(f"Groq API Error Output: {groq_response.text}") # Look at your console logs!
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail=f"Groq Stage 1 summary failed with status {groq_response.status_code}"
            )
            
        cv_summary = groq_response.json()["choices"][0]["message"]["content"]
        
        
        stage2_system = (
            "You are an AI HR Director. Based on a candidate's structural CV profile, "
            "determine their primary matching technical title. You MUST reply with only "
            "the raw title string from standard engineering titles (e.g., 'ML Engineer', "
            "'Backend Engineer', 'Frontend Engineer', 'DevOps Engineer'). No extra words."
        )
        

        # hf_response = await client.post(
        #     str(HF_API_URL),
        #     headers={
        #         "Authorization": f"Bearer {HF_API_KEY}",
        #         "Content-Type": "application/json"
        #     },
        #     json={
        #         "model": HF_LLM_MODEL,
        #         "messages": [
        #             {"role": "system", "content": stage2_system},
        #             {"role": "user", "content": f"Candidate Profile Summary:\n{cv_summary}"}
        #         ],
        #         "temperature": 0.0
        #     },
        #     timeout=60.0
        # )
        
        # if hf_response.status_code != 200:
        #     print(f"Hugging Face Error Output: {hf_response.text}")
        #     raise HTTPException(
        #         status_code=status.HTTP_502_BAD_GATEWAY, 
        #         detail="Hugging Face Stage 2 classification failed."
        #     )
            
        # final_job_role = hf_response.json()["choices"][0]["message"]["content"]
        
        # # Strip any accidental whitespace or punctuation from the model output
        # return final_job_role.strip().replace("'", "").replace('"', '')

        formatted_messages = [{"role": "system", "content": stage2_system},
        {"role": "user", "content": f"Candidate Profile Summary:\n{cv_summary}"}]
        

        # Match Nvidia's target structural payload constraints
        payload = {
            "model": f"{NVIDIA_LLM_MODEL}",
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

