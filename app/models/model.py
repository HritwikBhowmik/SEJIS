
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# 1. Define the base class for all SQLAlchemy models
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationship to cleanly pull all interview scores belonging to this user
    # loading='selectin' is recommended for asynchronous setups
    scores: Mapped[list["InterviewScore"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class InterviewScore(Base):
    __tablename__ = "interview_scores"

    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Core Parameters
    for_jobrole: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Evaluation Segment 1: Introduction
    intro_score: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    intro_eval_report: Mapped[str] = mapped_column(Text, nullable=True)

    # Evaluation Segment 2: Data Structures & Algorithms
    dsa_score: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    dsa_eval_report: Mapped[str] = mapped_column(Text, nullable=True)

    # Evaluation Segment 3: System Design
    sysd_score: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    sysd_eval_report: Mapped[str] = mapped_column(Text, nullable=True)

    # Final Summary Conclusions
    final_score: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    final_eval_report: Mapped[str] = mapped_column(Text, nullable=True)

    # total score
    total_score: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    # Relationship linking back up to the User profile
    user: Mapped["User"] = relationship(back_populates="scores")

    