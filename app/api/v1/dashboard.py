
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import datetime

from app.api.deps import get_current_user, get_async_db
from app.schemas.dashboard import ScoreBreakdown, InterviewDashboardRecord
from app.models.model import User, InterviewScore

router = APIRouter()


@router.get("/dashboard", response_model=List[InterviewDashboardRecord])
async def get_candidate_dashboard(current_user: User = Depends(get_current_user),
                                  db: AsyncSession = Depends(get_async_db)):
    """
    Fetches all completed interview session milestones for the currently logged-in candidate,
    ordered from newest to oldest.
    """
    try:
        # Query all scores belonging to the authenticated user ID
        # Adjust 'created_at' to match your model's timestamp column name if necessary
        query = (select(InterviewScore)
                .where(InterviewScore.user_id == current_user.id)
                .order_by(InterviewScore.created_at.desc()) if hasattr(InterviewScore, 'created_at') 
                else select(InterviewScore).where(InterviewScore.user_id == current_user.id))
        
        result = await db.execute(query)
        records = result.scalars().all()
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user workspace profile logs: {str(e)}")

    # Formulate response mapping payload array matching your frontend layout matrix
    dashboard_data = []
    for r in records:
        dashboard_data.append(
            InterviewDashboardRecord(
                id=str(r.id),
                job_role=r.for_jobrole,
                total_score=r.total_score,
                created_at=getattr(r, 'created_at', datetime.now()), # fallback timestamp handling
                intro=ScoreBreakdown(mark=r.intro_score, report=r.intro_eval_report),
                dsa=ScoreBreakdown(mark=r.dsa_score, report=r.dsa_eval_report),
                system_design=ScoreBreakdown(mark=r.sysd_score, report=r.sysd_eval_report),
                hr_final=ScoreBreakdown(mark=r.final_score, report=r.final_eval_report)
            )
        )

    return dashboard_data


