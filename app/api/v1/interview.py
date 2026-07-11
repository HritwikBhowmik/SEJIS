

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import json
import httpx
import re
import os
import uuid
from dotenv import load_dotenv

from app.api.deps import get_redis, get_current_user, get_async_db
from app.models.model import User, InterviewScore
from app.schemas.interview import InterviewChatPayload, InterviewStartResponse
from app.services.llm_client import generate_llm_response

load_dotenv()

router = APIRouter()

DSA_QUES = os.getenv('DSA_QUES_URL')

@router.get("/intro-ques", response_model=InterviewStartResponse)
async def start_interview(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):
    
    # Retrieve the role cached from the previous CV upload step
    role = await redis.hget(f"cv_review:{current_user.id}:role", 'role') # only saved role no extracted_text
    if not role:
        raise HTTPException(status_code=400, detail="Please upload a resume first.")
        
    session_id = str(uuid.uuid4())
    
    # Initialize the Redis cache history state
    session_data = {
        "student_id": str(current_user.id),
        "job_role": role.decode('utf-8') if isinstance(role, bytes) else role,
        "history": [] # Empty chat array to start
    }
    
    # Store interview session state in Redis (Expires in 2 hours for safety)
    # await redis.set(f"session:{session_id}", json.dumps(session_data), ex=7200)
    # await redis.hset(f"session:{session_id}", mapping={'session_data':json.dumps(session_data)})
    # await redis.expire(f"session:{session_id}", 7200)
    
    # Kick off the chat logic by generating the initial greeting from the LLM
    initial_prompt = f"You are an interviewer for an {session_data['job_role']} position. \
                       Greet the candidate and ask the first question (e.g Introduce yourself \
                       or tell me about yourself)."
    try:
        first_question = await generate_llm_response(system_prompt=initial_prompt, chat_history=[])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail=f"LLM service is currently unavailable: {str(e)}")
    
    # Save the LLM's opening question to the history
    session_data["history"].append({"role": "assistant", "content": first_question})
    await redis.set(f"session:{session_id}", json.dumps(session_data), ex=7200)
    # await redis.hset(f"session:{session_id}", mapping={'session_data':json.dumps(session_data)})
    # await redis.expire(f"session:{session_id}", 7200)

    return {"session_id": session_id, "initial_message": first_question}


@router.post("/dsa-ques")
async def dsa_ques(
    payload: InterviewChatPayload,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):

    # Fetch live context state from Redis cache
    raw_session = await redis.get(f"session:{payload.session_id}")

    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)#.decode('utf-8'))
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")
        
    # Append candidate's new reply to history
    session_data["history"].append({"role": "user", "content": payload.message})
    
    url = str(DSA_QUES)

    # Send the request with parameters, headers, and a timeout safety limit
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        json_data = response.json()
    # The external LeetCode API may return 'question' as a nested dict or a string.
    # Flatten it safely into a readable string before stripping HTML tags.
    raw_question = json_data.get('question', '')
    if isinstance(raw_question, dict):
        # Try common keys like 'content', 'body', 'text', or just join all string values
        question_text = raw_question.get('content') or raw_question.get('body') or raw_question.get('text') or ''
        if not question_text:
            question_text = ' '.join(str(v) for v in raw_question.values() if isinstance(v, str))
    elif isinstance(raw_question, list):
        question_text = ' '.join(str(item) for item in raw_question)
    else:
        question_text = str(raw_question)
    
    # Also grab the title if available
    title = json_data.get('questionTitle', json_data.get('title', ''))
    if isinstance(title, dict):
        title = title.get('title', '') or title.get('name', '') or ''
    
    # Strip HTML tags from the question text
    question = re.sub(r'<[^>]+>', '', question_text).strip()
    
    # Prepend the title if we have one
    if title and isinstance(title, str):
        question = title.strip() + '\n\n' + question
    
    # Cleans all hints and joins them with newlines automatically
    #all_hints = "\n".join(re.sub(r'<[^>]+>', '', hint) for hint in json_data['hints'])

    if not question :#and not all_hints:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED)

    message:str = "Question:\n" + question #+ "\n\n Hints:\n" + all_hints

    session_data["dsa_question"] = message # store the question for evaluation
    
    # Append question back to cache and save
    session_data["history"].append({"role": "assistant", "content": message})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)
    
    return {"dsa_ques": message}


@router.post("/sysd-ques")
async def sysd_ques(
    payload: InterviewChatPayload,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):

    # Fetch live context state from Redis cache
    raw_session = await redis.get(f"session:{payload.session_id}")

    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)#.decode('utf-8'))
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")
        
    # Append candidate's new reply to history
    session_data["history"].append({"role": "user", "content": payload.message})

    system_instruction = f"You are an expert technical interviewer evaluating a candidate \
                           for a {session_data['job_role']} position. Maintain context, ask the \
                           candidate a system design related question. (e.g How ChatGPT handles millions\
                           of user's requests and response in miliseconds, how spotify's playlist works, \
                           how amazon handles millions of transactions daily)"
    
    # Generate next reply asynchronously (Non-blocking)
    ai_response = await generate_llm_response(
        system_prompt=system_instruction, 
        chat_history=session_data["history"]
    )

    session_data['sysd_ques'] = ai_response
    
    # Append AI question back to cache and save
    session_data["history"].append({"role": "assistant", "content": ai_response})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)
    
    return {"sysd_ques": ai_response}


@router.post("/final-ques")
async def final_ques(
    payload: InterviewChatPayload,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)):

    # Fetch live context state from Redis cache
    raw_session = await redis.get(f"session:{payload.session_id}")

    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
        
    session_data = json.loads(raw_session)#.decode('utf-8'))
    
    # Guard check: Ensure this student owns this session
    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")
        
    # Append candidate's new reply to history
    session_data["history"].append({"role": "user", "content": payload.message})

    system_instruction = f"You are an expert HR interviewer evaluating a candidate \
                           for a {session_data['job_role']} position. Maintain context, ask the \
                           candidate about his/her salary expectation, or any formal questions\
                           that is asked at the end of the interview."
    
    # Generate next reply asynchronously (Non-blocking)
    ai_response = await generate_llm_response(
        system_prompt=system_instruction, 
        chat_history=session_data["history"]
    )
    
    session_data['final_ques'] = ai_response

    # Append AI question back to cache and save
    session_data["history"].append({"role": "assistant", "content": ai_response})
    await redis.set(f"session:{payload.session_id}", json.dumps(session_data), ex=7200)
    
    return {"sysd_ques": ai_response}


@router.post("/submit-interview")
async def submit_and_save_interview(session_id:str,
                                   current_user: User = Depends(get_current_user),
                                   redis: Redis = Depends(get_redis),
                                   db: AsyncSession = Depends(get_async_db)):

    raw_session = await redis.get(f"session:{session_id}")

    if not raw_session:
        raise HTTPException(status_code=440, detail="Interview session expired or invalid")
    
    session_data = json.loads(raw_session)

    if session_data["student_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Unauthorized session access")

    # Define the 4 Redis keys where individual stage results are cached
    intro_key = f"all:{current_user.id}:user_intro_scores"
    dsa_key   = f"all:{current_user.id}:user_dsa_scores"
    sysd_key  = f"all:{current_user.id}:user_sysd_scores"
    final_key = f"all:{current_user.id}:user_final_scores"

    # Extract data safely from Redis hashes using hgetall
    # Using hgetall captures 'mark' and 'report' fields simultaneously per hash map
    intro_data = await redis.hgetall(intro_key)
    dsa_data   = await redis.hgetall(dsa_key)
    sysd_data  = await redis.hgetall(sysd_key)
    final_data = await redis.hgetall(final_key)

    # Guard Check: Ensure they didn't bypass sections (Intro and DSA are mandatory to submit)
    if not intro_data or not dsa_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit. Missing required interview component caches. Please complete your loops."
        )

    # Helper function to parse values cleanly regardless of your Redis 'decode_responses' configuration
    def parse_redis_hash(data_dict):
        if not data_dict:
            return 0, "No evaluation submitted."
        
        # Binary bytes handling fallback wrapper
        raw_mark = data_dict.get(b'mark', data_dict.get('mark', b'0'))
        raw_report = data_dict.get(b'report', data_dict.get('report', b''))
        
        # Decode byte structures out to clean strings
        mark_str = raw_mark.decode('utf-8') if isinstance(raw_mark, bytes) else str(raw_mark)
        report_str = raw_report.decode('utf-8') if isinstance(raw_report, bytes) else str(raw_report)
        
        return int(mark_str) if mark_str.isdigit() else 0, report_str

    # Process structural evaluations
    job_role = session_data['job_role']
    intro_mark, intro_report = parse_redis_hash(intro_data)
    dsa_mark, dsa_report = parse_redis_hash(dsa_data)
    sysd_mark, sysd_report = parse_redis_hash(sysd_data)
    final_mark, final_report = parse_redis_hash(final_data)

    # Calculate total overall compiled matrix score 
    total_score = intro_mark + dsa_mark + sysd_mark + final_mark

    # Instatitate your SQLAlchemy record map
    db_score = InterviewScore(
        user_id=current_user.id,
        for_jobrole=job_role,
        intro_score=intro_mark,
        intro_eval_report=intro_report,
        dsa_score=dsa_mark,
        dsa_eval_report=dsa_report,
        sysd_score=sysd_mark,
        sysd_eval_report=sysd_report,
        final_score=final_mark,
        final_eval_report=final_report,
        total_score=total_score
    )

    try:
        # Commit permanently to PostgreSQL 
        db.add(db_score)
        await db.commit()
        await db.refresh(db_score)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database engine write exception: {str(e)}"
        )

    # Post-Commit Pipeline Cleanup: Purge cache states since data is now persistent
    # This prevents old score data states bleeding into future interview rounds!
    cleanup_keys = [intro_key, dsa_key, sysd_key, final_key, f"session:{session_id}"]
    await redis.delete(*cleanup_keys)

    return {
        "status": "success",
        "message": "All interview evaluation steps permanently archived.",
        "total_score": total_score,
        "record_id": str(db_score.id) if hasattr(db_score, 'id') else None
    }
