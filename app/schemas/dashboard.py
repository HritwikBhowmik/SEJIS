
from pydantic import BaseModel
from datetime import datetime

class ScoreBreakdown(BaseModel):
    mark: int
    report: str

class InterviewDashboardRecord(BaseModel):
    id: str
    job_role: str
    total_score: int
    created_at: datetime
    # Nested breakdown blocks make it simple for frontend mapping
    intro: ScoreBreakdown
    dsa: ScoreBreakdown
    system_design: ScoreBreakdown
    hr_final: ScoreBreakdown

    class Config:
        from_attributes = True
