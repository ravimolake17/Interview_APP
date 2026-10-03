"""Response models for the dynamic resume-extraction pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResumeSection(BaseModel):
    """One dynamically discovered section of a resume."""

    model_config = ConfigDict(extra="allow")

    section_id: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    heading_source: Literal["original", "inferred"] = "original"
    order: int = Field(default=0, ge=0)
    content_type: Literal["text", "list", "table", "key_value"] = "text"
    items: list[Any] = Field(default_factory=list)
    raw_text: str = ""

    @field_validator("section_id", "heading")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Resume section identifiers and headings cannot be empty.")
        return cleaned


class ParsedResume(BaseModel):
    """The complete dynamic extraction result in source order."""

    model_config = ConfigDict(extra="allow")

    sections: list[ResumeSection] = Field(default_factory=list, min_length=1)
    source_text: str = ""
    extraction_method: str = ""
    extraction_warning: str = ""


class ResumeResponse(BaseModel):
    """Validated API response returned by the resume upload endpoint."""

    model_config = ConfigDict(extra="allow")

    status: Literal["success"] = "success"
    original_filename: str = ""
    stored_file_url: str = ""
    pages: int = Field(default=0, ge=0)
    parsed_data: ParsedResume
