
from pydantic import BaseModel


class InterviewChatPayload(BaseModel):
    session_id:str
    message:str

class InterviewDSAPayload(BaseModel):
    session_id:str
    code:str

class InterviewStartResponse(BaseModel):
    session_id:str
    initial_message:str

class InterviewEvalRespose(BaseModel):
    mark:int
    report:str


