from fastapi import APIRouter

from agents.screening_agent.schemas.ats import MatchAnalysis, MatchingAnalyzeRequest
from agents.screening_agent.services.matching_service import analyze_skill_match

router = APIRouter(prefix="/api/matching", tags=["Matching"])


@router.post("/analyze", response_model=MatchAnalysis)
def analyze_matching(payload: MatchingAnalyzeRequest) -> MatchAnalysis:
    return analyze_skill_match(payload.candidate_skills, payload.parsed_jd)
