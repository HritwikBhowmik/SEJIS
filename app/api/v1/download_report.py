
import io
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from weasyprint import HTML

from app.api.deps import get_current_user, get_async_db
from app.models.model import User, InterviewScore

router = APIRouter()

@router.get("/interview/{record_id}/pdf")
async def download_interview_report_pdf(record_id: str,
                                        current_user: User = Depends(get_current_user),
                                        db: AsyncSession = Depends(get_async_db)):
    """
    Fetches a specific interview record, confirms user ownership, 
    renders a beautifully designed PDF on the fly via WeasyPrint, and streams it.
    """
    # Fetch the specific score record from PostgreSQL
    try:
        query = select(InterviewScore).where(InterviewScore.id == record_id)
        result = await db.execute(query)
        record = result.scalars().first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database lookup error: {str(e)}"
        )

    # Guard Check: Ensure record exists and belongs to the logged-in candidate
    if not record:
        raise HTTPException(status_code=404, detail="Interview report record not found.")
        
    if record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this report.")

    # Create a clean, modern HTML Template inline
    # WeasyPrint perfectly executes modern CSS (flexbox, borders, Google Fonts, page breaks)
    created_date = getattr(record, 'created_at', None)
    formatted_date = created_date.strftime("%B %d, %Y") if created_date else "Recent Session"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Interview Evaluation Report</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            @page {{
                size: A4;
                margin: 20mm;
            }}
            body {{
                font-family: 'Inter', sans-serif;
                color: #1e293b;
                line-height: 1.5;
                margin: 0;
                padding: 0;
            }}
            .header {{
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 15px;
                margin-bottom: 30px;
            }}
            .header h1 {{
                font-size: 24px;
                color: #0f172a;
                margin: 0 0 5px 0;
            }}
            .meta-grid {{
                display: flex;
                justify-content: space-between;
                font-size: 14px;
                color: #64748b;
            }}
            .total-score-box {{
                background-color: #f1f5f9;
                border-left: 4px solid #3b82f6;
                padding: 15px;
                margin-bottom: 30px;
                border-radius: 4px;
            }}
            .total-score-box h2 {{
                margin: 0;
                font-size: 18px;
                color: #1e3a8a;
            }}
            .total-score-box .score {{
                font-size: 28px;
                font-weight: 700;
                color: #2563eb;
                margin-top: 5px;
            }}
            .section {{
                margin-bottom: 25px;
                page-break-inside: avoid;
            }}
            .section-title {{
                font-size: 16px;
                font-weight: 700;
                color: #0f172a;
                border-bottom: 1px solid #cbd5e1;
                padding-bottom: 4px;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
            }}
            .badge {{
                background-color: #e0f2fe;
                color: #0369a1;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            .report-text {{
                font-size: 14px;
                color: #334155;
                background-color: #fafafa;
                padding: 12px;
                border-radius: 4px;
                border: 1px solid #f0f0f0;
                margin-top: 5px;
                font-style: italic;
            }}
        </style>
    </head>
    <body>

        <div class="header">
            <h1>AI Technical Interview Performance Report</h1>
            <div class="meta-grid">
                <div><strong>Candidate Name:</strong> {getattr(current_user, 'full_name', 'Verified Candidate')}</div>
                <div><strong>Target Role:</strong> {record.for_jobrole}</div>
            </div>
            <div class="meta-grid" style="margin-top: 5px;">
                <div><strong>Date Generated:</strong> {formatted_date}</div>
                <div><strong>Report Token ID:</strong> {record_id[:8]}...</div>
            </div>
        </div>

        <div class="total-score-box">
            <h2>Overall Cumulative Assessment Score</h2>
            <div class="score">{record.total_score} <span style="font-size: 14px; font-weight: normal; color: #64748b;">/ 350 pts Total Matrix</span></div>
        </div>

        <!-- 1. INTRODUCTORY SEGMENT -->
        <div class="section">
            <div class="section-title">
                <span>1. Communication & Professional Alignment</span>
                <span class="badge">Score: {record.intro_score} / 50</span>
            </div>
            <div class="report-text">"{record.intro_eval_report}"</div>
        </div>

        <!-- 2. DATA STRUCTURES & ALGORITHMS -->
        <div class="section">
            <div class="section-title">
                <span>2. Data Structures & Algorithmic Optimization</span>
                <span class="badge">Score: {record.dsa_score} / 100</span>
            </div>
            <div class="report-text">"{record.dsa_eval_report}"</div>
        </div>

        <!-- 3. SYSTEM DESIGN -->
        <div class="section">
            <div class="section-title">
                <span>3. Scalable Architecture & System Design</span>
                <span class="badge">Score: {record.sysd_score} / 100</span>
            </div>
            <div class="report-text">"{record.sysd_eval_report}"</div>
        </div>

        <!-- 4. HR FINAL ROUND -->
        <div class="section">
            <div class="section-title">
                <span>4. Expectation Matching & Negotiation</span>
                <span class="badge">Score: {record.final_score} / 50</span>
            </div>
            <div class="report-text">"{record.final_eval_report}"</div>
        </div>

    </body>
    </html>
    """

    # Generate the PDF entirely in-memory using an asynchronous execution context
    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
        pdf_io = io.BytesIO(pdf_bytes or b'')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pray to God, WeasyPrint rendering engine crashed: {str(e)}"
        )

    # Build dynamic professional filename layout
    clean_role_name = record.for_jobrole.lower().replace(" ", "-").replace("(", "").replace(")", "")
    filename = f"interview-report-{clean_role_name}.pdf"

    # Stream file binary to browser instantly triggering file save
    return StreamingResponse(pdf_io,
                            media_type="application/pdf",
                            headers={
                                "Content-Disposition": f"attachment; filename={filename}"
                            })

