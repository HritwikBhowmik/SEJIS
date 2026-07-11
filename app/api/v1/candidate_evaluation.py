
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from redis.asyncio import Redis
import json
import re
import io
from PIL import Image

from app.api.deps import get_redis, get_current_user
from app.models.model import User
from app.schemas.interview import InterviewChatPayload, \
                                  InterviewDSAPayload, \
                                  InterviewEvalRespose
from app.services.llm_client import generate_llm_response,\
                                    generate_mm_response


router = APIRouter()


@router.post("/intro-eval", response_model=InterviewEvalRespose)
async def start_interview(
    payload:InterviewChatPayload,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):
    
    # Retrieve the role cached from the previous CV upload step
    raw_session = await redis.get(f"session:{payload.session_id}")
    
    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)#.decode('utf-8'))
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")
        
    # Append candidate's new reply to history
    session_data["history"].append({"role": "user", "content": payload.message})

    system_instruction = f"""You are an expert technical interviewer evaluating a candidate for \
        a {session_data['job_role']} position. You asked the candidate to tell him/her about himself/herself.

    Stictly evaluate the candidate's response based on whether they speak clearly in fluent English and \
        accurately describe the key capabilities of their job role.

    You MUST respond ONLY with a raw JSON object containing exactly two keys: "mark" (an integer out of 50) \
        and "report" (a 3 to 4 line short review highlighting weak or strong points). Do not include any \
            markdown fences or conversational filler.

    Example Format:
    {{"mark": 40, "report": "The candidate speaks clearly and correctly identifies system architecture as \
        a key capability. However, they lacked depth when discussing database optimization techniques."}}"""
    
    try:
        ai_response = await generate_llm_response(system_prompt=system_instruction, 
                                                  chat_history=session_data["history"])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail=f"LLM service is currently unavailable: {str(e)}")

    try:
        # Clean the response string in case the model added markdown ```json wrappers
        cleaned_response = re.sub(r"```json|```", "", ai_response).strip()
        evaluation_data = json.loads(cleaned_response)
        
        # Ensure keys match what you expect
        mark = evaluation_data.get("mark", 0)
        report = evaluation_data.get("report", "Failed to generate report.")
    except (json.JSONDecodeError, Exception):
        # Fallback default if the model misbehaves
        mark = 0
        report = ai_response

    
    # Append AI question back to cache and save
    session_data["history"].append({"role": "assistant", "content": report})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)

    await redis.hset(f"all:{current_user.id}:user_intro_scores",
                     mapping={'mark':mark, "report":report})
    await redis.expire(f"all:{current_user.id}:user_intro_scores", 7200)

    return {"mark":mark, "report": report}


@router.post('/dsa-eval', response_model=InterviewEvalRespose)
async def dsa_eval(payload:InterviewDSAPayload,
                   current_user: User = Depends(get_current_user),
                   redis: Redis = Depends(get_redis)):
    
    raw_session = await redis.get(f'session:{payload.session_id}')

    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
    
    session_data = json.loads(raw_session)

    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    formatted_code_message = f"Here is my code solution:\n```python\n{payload.code}\n```"
    session_data["history"].append({"role": "user", "content": formatted_code_message})

    dsa_question = session_data.get("dsa_question", "Analyze the candidate's code structure.")

    system_instruction = f"""You are an expert technical interviewer evaluating a candidate for a {session_data['job_role']} position.
You asked the candidate the following DSA question:
{dsa_question}

Evaluate the candidate's code answer based on correctness, time complexity, and edge cases.

You MUST respond ONLY with a raw JSON object containing exactly two keys: "mark" (an integer out of 100) and "report" (a 3 to 4 line short review highlighting weak or strong points). Do not include any markdown fences or conversational filler.

Example Format:
{{"mark": 70, "report": "The program solves the problem, but an O(N) or O(N log N) approach would optimize space complexities significantly."}}"""

    try:
        ai_response = await generate_llm_response(system_prompt=system_instruction, 
                                                  chat_history=session_data["history"])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail=f"LLM service is currently unavailable: {str(e)}")

    try:
        # Clean the response string in case the model added markdown ```json wrappers
        cleaned_response = re.sub(r"```json|```", "", ai_response).strip()
        evaluation_data = json.loads(cleaned_response)
        
        # Ensure keys match what you expect
        mark = evaluation_data.get("mark", 0)
        report = evaluation_data.get("report", "Failed to generate report.")
    except (json.JSONDecodeError, Exception):
        # Fallback default if the model misbehaves
        mark = 0
        report = ai_response

    
    # Append AI question back to cache and save
    session_data["history"].append({"role": "assistant", "content": report})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)

    await redis.hset(f"all:{current_user.id}:user_dsa_scores",
                     mapping={'mark':mark, "report":report})
    await redis.expire(f"all:{current_user.id}:user_dsa_scores", 7200)

    return {"mark":mark, "report": report}


@router.post("/sysd-eval", response_model=InterviewEvalRespose)
async def system_evaluation(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)
):
    # Fetch live context state from Redis cache
    raw_session = await redis.get(f"session:{session_id}")
    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    # Validate that the uploaded file is an image
    if not (file.content_type and file.content_type.startswith("image/")):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid image format.")

    try:
        # Read file bytes and convert safely into a PIL Image object
        image_bytes = await file.read()
        pil_image = Image.open(io.BytesIO(image_bytes))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image file.")

    # Formulate structural system design evaluation prompt
    job_role = session_data.get("job_role")
    
    # If you tracked the specific architecture prompt question earlier, fetch it here:
    system_question = session_data.get("sysd_ques")

    system_instruction = f"""
    You are an expert technical interviewer evaluating a candidate for a {job_role} position.
    The candidate was asked the following System Design question:
    "{system_question}"

    Analyze the submitted system architecture diagram carefully. Check for scalability bottlenecks, 
    single points of failure (SPOFs), appropriate database choices, caching strategy, and security layers.

    You MUST return your evaluation as a clean JSON object containing exactly two fields:
    - "mark": an integer from 0 to 100 representing the score.
    - "report": a short, 3 to 4 line concise technical review highlighting specific architectural strengths or weaknesses.
    """

    try:
        # Request multimodal inference using the modern client structure
        ai_response = await generate_mm_response(pil_image=pil_image, system_instruction=system_instruction)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"GenAI platform failed to process image asset: {str(e)}"
        )

    # Extract structured results safely
    try:
        evaluation_data = json.loads(ai_response or "")
        mark = evaluation_data.get("mark", 0)
        report = evaluation_data.get("report", "Failed to generate report text.")
    except (json.JSONDecodeError, Exception):
        # Fallback parsing safety loop
        mark = 0
        report = ai_response

    # Append structural review string to chat log for continuity
    session_data["history"].append({
        "role": "user", 
        "content": "[Submitted System Design Architecture Diagram Asset]"
    })
    session_data["history"].append({
        "role": "assistant", 
        "content": f"System Evaluation Report:\n{report}"
    })
    
    # Save session state updates
    await redis.set(f"session:{session_id}", json.dumps(session_data), ex=7200)
    
    # Persist evaluation score state block to user scoring workspace hash
    await redis.hset(
        f"all:{current_user.id}:user_sysd_scores",
        mapping={'mark': mark or 0, "report": report or ""}
    )
    await redis.expire(f"all:{current_user.id}:user_sysd_scores", 7200)

    return {"mark": mark, "report": report}


@router.post("/final-eval", response_model=InterviewEvalRespose)
async def final_interview(
    payload:InterviewChatPayload,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):
    
    # Retrieve the role cached from the previous CV upload step
    raw_session = await redis.get(f"session:{payload.session_id}")
    
    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)#.decode('utf-8'))
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")
        
    # Append candidate's new reply to history
    session_data["history"].append({"role": "user", "content": payload.message})

    final_ques:str = session_data.get("final_ques")

    system_instruction = f"""You are an expert technical interviewer evaluating a candidate for \
        a {session_data['job_role']} position. You asked the candidate this particular question: \n{final_ques}.

    Stictly evaluate the candidate's response based on whether they speak clearly in fluent English and \
        accurately describe their salary expectations. Check if their expectations fair or not, also give \
        mark on the basis of their research on the market.

    You MUST respond ONLY with a raw JSON object containing exactly two keys: "mark" (an integer out of 50) \
        and "report" (a 3 to 4 line short review highlighting weak or strong points). Do not include any \
            markdown fences or conversational filler.

    Example Format:
    {{"mark": 40, "report": "The candidate asked for a very high salary which is unfair, because the \
        the salary range inappropiate for {session_data['job_role']}. The candidate could not research \
            well."}}"""
    
    try:
        ai_response = await generate_llm_response(system_prompt=system_instruction, 
                                                  chat_history=session_data["history"])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail=f"LLM service is currently unavailable: {str(e)}")

    try:
        # Clean the response string in case the model added markdown ```json wrappers
        cleaned_response = re.sub(r"```json|```", "", ai_response).strip()
        evaluation_data = json.loads(cleaned_response)
        
        # Ensure keys match what you expect
        mark = evaluation_data.get("mark", 0)
        report = evaluation_data.get("report", "Failed to generate report.")
    except (json.JSONDecodeError, Exception):
        # Fallback default if the model misbehaves
        mark = 0
        report = ai_response

    
    # Append AI question back to cache and save
    session_data["history"].append({"role": "assistant", "content": report})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)
    
    await redis.hset(f"all:{current_user.id}:user_final_scores",
                     mapping={'mark':mark, "report":report})
    await redis.expire(f"all:{current_user.id}:user_final_scores", 7200)

    return {"mark":mark, "report": report}


