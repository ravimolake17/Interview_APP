import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from agents.screening_agent.schemas.ats import JDParseRequest, JDUploadResponse, ParsedJD
from agents.screening_agent.services.docling_extractor import DoclingConversionError, DoclingDependencyError
from agents.screening_agent.services.document_ingestion import ingest_document
from agents.screening_agent.services.jd_parser import parse_job_description
from services.job_position import job_title_from_jd_content

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jd", tags=["Job Description"])


def _with_jd_content_title(parsed: ParsedJD, jd_text: str) -> ParsedJD:
    title = job_title_from_jd_content(jd_text=jd_text, parsed_job_title=parsed.job_title)
    if title and title != "Open Position":
        parsed.job_title = title
    return parsed


@router.post("/parse", response_model=ParsedJD)
def parse_jd(payload: JDParseRequest) -> ParsedJD:
    try:
        return _with_jd_content_title(parse_job_description(payload.jd_text), payload.jd_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("JD parsing failed")
        raise HTTPException(status_code=500, detail="Unable to parse the job description.") from exc


@router.post("/upload", response_model=JDUploadResponse)
async def upload_jd(file: UploadFile = File(...)) -> JDUploadResponse:
    try:
        extracted = await ingest_document(file, "jds")
        parsed_jd = _with_jd_content_title(
            parse_job_description(extracted["text"]),
            extracted["text"],
        )
        return JDUploadResponse(
            status="success",
            original_filename=extracted["original_filename"],
            stored_file_url=extracted["stored_url"],
            jd_text=extracted["text"],
            parsed_jd=parsed_jd,
        )
    except HTTPException:
        raise
    except DoclingDependencyError as exc:
        logger.exception("JD upload dependency is unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DoclingConversionError as exc:
        logger.exception("JD document conversion failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("JD upload parsing failed")
        raise HTTPException(status_code=500, detail="Unable to process the uploaded JD file.") from exc
