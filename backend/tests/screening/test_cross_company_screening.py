"""Candidates are identified by email and cannot be screened at a second company."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.candidate import CandidateStatus
from services.screening_integration_service import (
    CandidateAlreadyScreenedElsewhereError,
    emails_from_parsed_resume,
    ensure_not_screened_elsewhere,
    is_placeholder_email,
    normalize_candidate_emails,
    set_candidate_contact_email,
)


def test_placeholder_emails_are_not_identity():
    assert is_placeholder_email(None)
    assert is_placeholder_email("")
    assert is_placeholder_email("no-email-abc@screening.local")
    assert is_placeholder_email("NO-EMAIL-x@SCREENING.LOCAL")
    assert not is_placeholder_email("jane@company.com")


def test_normalize_drops_placeholders_and_duplicates():
    assert normalize_candidate_emails(
        "Jane@Company.com",
        "jane@company.com",
        "no-email-1@screening.local",
        None,
        "  other@x.com ",
    ) == ["jane@company.com", "other@x.com"]


def test_error_message_includes_email_and_company():
    err = CandidateAlreadyScreenedElsewhereError("jane@x.com", "RR Parkon")
    assert "jane@x.com" in str(err)
    assert "RR Parkon" in str(err)
    assert "cannot be screened at another company" in str(err)


def test_emails_from_parsed_resume_reads_section_text():
    emails = emails_from_parsed_resume(
        {
            "sections": [
                {"raw_text": "Asha Patil\nasha@example.com", "items": []},
            ],
            "source_text": "",
        }
    )
    assert emails == ["asha@example.com"]


@pytest.mark.asyncio
async def test_ensure_allows_same_company_rescreen():
    repo = AsyncMock()
    repo.list_by_email.return_value = [MagicMock()]

    with patch(
        "services.screening_integration_service.CandidateRepository",
        return_value=repo,
    ):
        await ensure_not_screened_elsewhere(
            AsyncMock(), emails=["jane@x.com"], company_id=1
        )

    repo.get_by_email_outside_company.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_blocks_other_company():
    other = MagicMock()
    other.company_id = 2
    company = MagicMock()
    company.name = "RR Parkon"
    repo = AsyncMock()
    repo.list_by_email.return_value = []
    repo.get_by_email_outside_company.return_value = other
    companies = AsyncMock()
    companies.get_by_id.return_value = company

    with (
        patch(
            "services.screening_integration_service.CandidateRepository",
            return_value=repo,
        ),
        patch(
            "services.screening_integration_service.CompanyRepository",
            return_value=companies,
        ),
    ):
        with pytest.raises(CandidateAlreadyScreenedElsewhereError, match="RR Parkon"):
            await ensure_not_screened_elsewhere(
                AsyncMock(), emails=["jane@x.com"], company_id=1
            )


@pytest.mark.asyncio
async def test_ensure_skips_when_email_is_missing_or_placeholder():
    repo = AsyncMock()
    with patch(
        "services.screening_integration_service.CandidateRepository",
        return_value=repo,
    ):
        await ensure_not_screened_elsewhere(AsyncMock(), emails=[], company_id=1)
        await ensure_not_screened_elsewhere(
            AsyncMock(),
            emails=["no-email-ab@screening.local"],
            company_id=1,
        )
    repo.list_by_email.assert_not_called()
    repo.get_by_email_outside_company.assert_not_called()


@pytest.mark.asyncio
async def test_set_contact_email_rejects_after_invite_sent():
    candidate = MagicMock()
    candidate.email = "jane@x.com"
    candidate.status = CandidateStatus.SHORTLISTED
    candidate.candidate_id = "CAND-1"
    repo = AsyncMock()
    repo.get_by_candidate_id.return_value = candidate
    tokens = AsyncMock()
    tokens.has_any_token.return_value = True
    with (
        patch(
            "services.screening_integration_service.CandidateRepository",
            return_value=repo,
        ),
        patch(
            "services.screening_integration_service.has_booked_slot",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.screening_integration_service.TokenRepository",
            return_value=tokens,
        ),
    ):
        with pytest.raises(ValueError, match="after the scheduling invite was sent"):
            await set_candidate_contact_email(AsyncMock(), "CAND-1", "new@x.com")


@pytest.mark.asyncio
async def test_set_contact_email_updates_placeholder():
    candidate = MagicMock()
    candidate.email = "no-email-ab@screening.local"
    candidate.status = CandidateStatus.SHORTLISTED
    candidate.company_id = 1
    candidate.candidate_id = "CAND-1"
    candidate.evaluation_snapshot = {"candidate_details": {"emails": []}}
    repo = AsyncMock()
    repo.get_by_candidate_id.return_value = candidate
    tokens = AsyncMock()
    tokens.has_any_token.return_value = False

    with (
        patch(
            "services.screening_integration_service.CandidateRepository",
            return_value=repo,
        ),
        patch(
            "services.screening_integration_service.has_booked_slot",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.screening_integration_service.TokenRepository",
            return_value=tokens,
        ),
        patch(
            "services.screening_integration_service.ensure_not_screened_elsewhere",
            new_callable=AsyncMock,
        ),
        patch("services.screening_integration_service.flag_modified"),
    ):
        repo.list_by_email.return_value = []
        updated = await set_candidate_contact_email(
            AsyncMock(), "CAND-1", "Jane@X.com"
        )

    assert updated.email == "jane@x.com"
    assert updated.evaluation_snapshot["candidate_details"]["emails"] == ["jane@x.com"]


@pytest.mark.asyncio
async def test_set_contact_email_updates_not_sent_candidate():
    candidate = MagicMock()
    candidate.email = "parkon.1@tenancy.test"
    candidate.status = CandidateStatus.SHORTLISTED
    candidate.company_id = 1
    candidate.candidate_id = "CAND-1"
    candidate.evaluation_snapshot = {"candidate_details": {"emails": ["parkon.1@tenancy.test"]}}
    repo = AsyncMock()
    repo.get_by_candidate_id.return_value = candidate
    tokens = AsyncMock()
    tokens.has_any_token.return_value = False

    with (
        patch(
            "services.screening_integration_service.CandidateRepository",
            return_value=repo,
        ),
        patch(
            "services.screening_integration_service.has_booked_slot",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.screening_integration_service.TokenRepository",
            return_value=tokens,
        ),
        patch(
            "services.screening_integration_service.ensure_not_screened_elsewhere",
            new_callable=AsyncMock,
        ),
        patch("services.screening_integration_service.flag_modified"),
    ):
        repo.list_by_email.return_value = []
        updated = await set_candidate_contact_email(
            AsyncMock(), "CAND-1", "updated@example.com"
        )

    assert updated.email == "updated@example.com"


@pytest.mark.asyncio
async def test_set_contact_email_rejects_duplicate_used_by_another_candidate():
    candidate = MagicMock()
    candidate.email = "no-email-ab@screening.local"
    candidate.status = CandidateStatus.NEEDS_REVIEW
    candidate.company_id = 1
    candidate.candidate_id = "CAND-NEW"
    candidate.evaluation_snapshot = {"candidate_details": {"emails": []}}
    other = MagicMock()
    other.candidate_id = "CAND-OLD"
    other.email = "ashapatil@example.com"
    repo = AsyncMock()
    repo.get_by_candidate_id.return_value = candidate
    repo.list_by_email.return_value = [other]
    tokens = AsyncMock()
    tokens.has_any_token.return_value = False

    with (
        patch(
            "services.screening_integration_service.CandidateRepository",
            return_value=repo,
        ),
        patch(
            "services.screening_integration_service.has_booked_slot",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.screening_integration_service.TokenRepository",
            return_value=tokens,
        ),
        patch(
            "services.screening_integration_service.ensure_not_screened_elsewhere",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ValueError, match="already assigned to another candidate"):
            await set_candidate_contact_email(
                AsyncMock(), "CAND-NEW", "AshaPatil@example.com"
            )


def test_join_error_includes_company_brand():
    from types import SimpleNamespace

    from api.routes.interview import _join_http_error

    company = SimpleNamespace(name="RR Parkon", code="RRPARKON")
    exc = _join_http_error(403, "The interview room opens at 11:25 AM.", company)
    assert exc.status_code == 403
    assert exc.detail["message"].startswith("The interview room opens")
    assert exc.detail["company_name"] == "RR Parkon"
    assert exc.detail["company_code"] == "RRPARKON"
