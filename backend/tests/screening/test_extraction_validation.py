import zipfile

import pytest
from fastapi import HTTPException

from agents.screening_agent.routes.extract import _validate_docx_container


def _write_minimal_docx(path, payload: bytes = b"<w:document/>"):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", payload)


def test_valid_docx_container_passes_safety_validation(tmp_path):
    path = tmp_path / "resume.docx"
    _write_minimal_docx(path)

    _validate_docx_container(str(path), max_uncompressed_bytes=10_000)


def test_expanded_docx_size_limit_blocks_zip_bomb_pattern(tmp_path):
    path = tmp_path / "oversized.docx"
    _write_minimal_docx(path, payload=b"x" * 2_000)

    with pytest.raises(HTTPException) as exc_info:
        _validate_docx_container(str(path), max_uncompressed_bytes=1_000)

    assert exc_info.value.status_code == 413
