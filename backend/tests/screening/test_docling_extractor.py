from agents.screening_agent.services import docling_extractor


def test_never_mode_uses_embedded_text_without_initializing_docling(monkeypatch):
    monkeypatch.setattr(docling_extractor.settings, "PDF_OCR_MODE", "never")

    fallback_payload = {
        "pages": [{"page": 1, "text": "Anita Sharma Python FastAPI experience"}],
        "full_text": (
            "Anita Sharma\nanita@example.com\nSKILLS\nPython\nFastAPI\n"
            "EXPERIENCE\nBackend Developer 2021 - 2024"
        ),
        "extraction_warning": "fallback used",
    }

    monkeypatch.setattr(
        docling_extractor,
        "_run_conversion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Docling must not initialize in never mode")
        ),
    )
    monkeypatch.setattr(
        docling_extractor,
        "_extract_pdf_text_fallback",
        lambda _file_path: fallback_payload.copy(),
    )

    result = docling_extractor._convert_pdf("resume.pdf")

    assert result["full_text"] == fallback_payload["full_text"]
    assert "without OCR" in result["extraction_warning"]


def test_auto_mode_falls_back_when_docling_pipeline_fails(monkeypatch):
    monkeypatch.setattr(docling_extractor.settings, "PDF_OCR_MODE", "auto")

    def fail_docling(_file_path: str, *, enable_ocr: bool):
        assert enable_ocr is False
        raise RuntimeError("layout model unavailable")

    fallback_payload = {
        "pages": [{"page": 1, "text": "Anita Sharma Python FastAPI experience"}],
        "full_text": (
            "Anita Sharma\nanita@example.com\nSKILLS\nPython\nFastAPI\n"
            "EXPERIENCE\nBackend Developer 2021 - 2024"
        ),
        "extraction_warning": "fallback used",
    }

    monkeypatch.setattr(docling_extractor, "_run_conversion", fail_docling)
    monkeypatch.setattr(
        docling_extractor,
        "_extract_pdf_text_fallback",
        lambda _file_path: fallback_payload,
    )

    result = docling_extractor._convert_pdf("resume.pdf")

    assert result == fallback_payload


def test_extract_text_serializes_overlapping_conversions(monkeypatch):
    import threading
    import time

    active = 0
    max_active = 0
    guard = threading.Lock()

    def fake_convert(file_path: str):
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with guard:
            active -= 1
        return {
            "pages": [{"page": 1, "text": file_path}],
            "full_text": file_path,
        }

    monkeypatch.setattr(docling_extractor, "_convert", fake_convert)

    results: list[str] = []

    def worker(path: str) -> None:
        payload = docling_extractor.extract_text_from_pdf(path)
        results.append(payload["full_text"])

    threads = [
        threading.Thread(target=worker, args=(f"resume-{index}.pdf",))
        for index in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert max_active == 1
    assert sorted(results) == ["resume-0.pdf", "resume-1.pdf", "resume-2.pdf", "resume-3.pdf"]

