
import io
from pypdf import PdfReader
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from redis.asyncio import Redis

from app.services.resume_parser import extract_jobrole_pdf
from app.api.deps import get_redis, get_current_user
from app.models.model import User

router = APIRouter()


@router.post("/cv-upload")
async def upload_pdf(file: UploadFile = File(...),
                     current_user:User = Depends(get_current_user),
                     redis: Redis=Depends(get_redis)):
    
    # Enforce validation to ensure only PDFs are accepted
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only PDF files are allowed."
        )
    
    # Read file stream asynchronously
    contents = await file.read()

    # Convert binary bytes into an in-memory stream object
    pdf_stream = io.BytesIO(contents)
    
    try:
        # Load stream directly into PyPDF
        reader = PdfReader(pdf_stream)
        extracted_text = ""
        
        # Loop through pages and assemble the string text layout
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
                
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to parse PDF layers: {str(e)}"
        )
    
    # Extract text and predict the role using your parsing service
    predicted_role = await extract_jobrole_pdf(extracted_text)


    # save to cache (redis) for further processing
    await redis.hset(f"cv_review:{current_user.id}:role", 
                     mapping={'role':predicted_role})
    await redis.expire(f"cv_review:{current_user.id}:role", 7200)
        
    return {
        'detected-role':f"Your are selected for {predicted_role}"
    }


