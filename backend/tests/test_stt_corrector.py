"""Tests for resume-driven STT correction (no over-correction of non-resume speech)."""

from agents.interview_agent.stt_corrector import (
    apply_deterministic_corrections,
    build_whisper_prompt,
    correct_transcript_with_resume,
    extract_resume_terms,
    strip_whisper_artifacts,
)

RAW_STT = (
    "Thank you for the opportunity. My name is Ravi Laxman Molake and I recently completed "
    "my MCA with specialization in artificial intelligence and Machine Learning. Over the past "
    "few years, I have focused on developing intelligent software solutions using Python, "
    "Deep Learning, Computer Vision and Fast API. My interest has always been in building "
    "the AI systems that solves real-world problems rather than just training the machine "
    "learning models. During my internship at a big data analysis lab at Aloysius College, "
    "I worked on a research project involving Dental Mesh Segmentation. This project involved "
    "processing the real-world DICOM medical data and building the Deep Learning model using "
    "the MeshSegNet PyTorch and MONAIR to perform pure vertex segmentation on dental meshes "
    "I have responsible for pre the data training the model optimizing its performance "
    "evaluating the results, and preparing it for deployment. The model achieved 92.5% accuracy "
    "and the research was approved Infinity Publication. This Experienced taught me how to "
    "build a reliable I Developed a complete AI application called Tater-Check which detects "
    "potato leaf disease using the EfficientNet Deep Learning Approach. Instead of stopping "
    "the full Software Development, I built a complete solution by creating the FastAPI "
    "backend to serve the prediction and the ReactJS frontend For the user to upload images "
    "and receive the predictions in real time The model achieves 99 accuracy The project was "
    "later published at the research paper Through this project, I gained ## EXPERIENCE "
    "(INTERNSHIP) lifecycle data preprocessing, model training, evaluation, Web Development, "
    "front-end integration, testing and deployment. For technical standpoint, Python is my "
    "primary Programming Languages. I have worked extensively with PyTorch, TensorFlow, "
    "Keras, OpenCV, FastAPI, NumPy, SQL Databases, Git and Linux. I understand the complete "
    "machine learning workflow including data collection, pre-processing, Software Engineering "
    "model selection hyperparameters tuning evaluation API development and deployment I also "
    "have a basic exposure to AWS services such as AC2 and S3 which has helped me to "
    "understand the cloud-based deployment concepts. Beyond the technical skills, I enjoy the "
    "software complex problems and continuously learning the new technologies. I believe the "
    "AI is I believe this role is valuable only when it delivers the practical business "
    "outcomes. So I always focus on building the scalable and maintainable solutions rather "
    "than just experimental models. I enjoyed collaborating with teams, understanding business "
    "requirements and converting them into production-ready applications. So I believe this "
    "role aligns I'm happy to share my background with you because it combines everything "
    "I'm passionate about about Python Developer, AI, machine learning, and back-end "
    "development. And deploying the intelligent applications, I'm confident."
)

RAVI_SNAPSHOT = {
    "skills": [
        "Python",
        "PyTorch",
        "TensorFlow",
        "FastAPI",
        "OpenCV",
        "MONAI",
        "MeshSegNet",
        "EfficientNetB0",
        "ReactJS",
        "AWS EC2",
        "AWS S3",
    ],
    "parsed_resume": {
        "projects": [
            {
                "title": "Tater-Check",
                "description": "Potato leaf disease detection using EfficientNetB0",
            },
            {
                "title": "3D Dental Mesh Segmentation",
                "description": "MeshSegNet PyTorch MONAI DICOM per-vertex segmentation",
            },
        ],
        "experience": [
            {
                "company": "Big Data Analytics Lab",
                "organization": "St. Aloysius College",
                "title": "Research Intern",
            },
        ],
        "education": [{"degree": "MCA", "institution": "AI and ML specialization"}],
        "source_text": (
            "Ravi Molake MCA AI ML Big Data Analytics Lab St. Aloysius College "
            "Tater-Check MeshSegNet MONAI EfficientNetB0 92.5% 99.57% EC2 S3 "
            "FastAPI ReactJS Dental Mesh Segmentation 3D DICOM per-vertex"
        ),
    },
}


def _ravi_terms():
    return extract_resume_terms(
        full_name="Ravi Molake",
        evaluation_snapshot=RAVI_SNAPSHOT,
        jd_text="Python Developer AI ML FastAPI backend",
        job_position="Python Developer",
    )


def test_fixes_clear_phonetic_misses():
    terms = _ravi_terms()
    text, corrections = apply_deterministic_corrections(
        "I used MONAIR and Fast API on AC2 with MeshSegNet.",
        resume_terms=terms,
        candidate_name="Ravi Molake",
        job_position="Python Developer",
    )
    assert "MONAI" in text
    assert "FastAPI" in text
    assert "EC2" in text
    assert "AWS EC2" not in text
    assert any(c["to"] == "MONAI" for c in corrections)


def test_does_not_inject_resume_numbers():
    text, _ = apply_deterministic_corrections(
        "The model achieves 99 accuracy.",
        resume_terms=_ravi_terms(),
        candidate_name="Ravi Molake",
        job_position="Python Developer",
    )
    assert "99.57" not in text
    assert "99 accuracy" in text or "99" in text


def test_does_not_replace_unrelated_phrases_with_resume_terms():
    text, corrections = apply_deterministic_corrections(
        RAW_STT,
        resume_terms=_ravi_terms(),
        candidate_name="Ravi Molake",
        job_position="Python Developer",
    )
    assert "Infinity Publication" in text
    assert not any("approved for publication" in c["to"].lower() for c in corrections)
    assert "Laxman" in text
    assert "Python Developer Learning" not in text
    assert "College Tater worked" not in text


def test_preserves_trailing_speech_not_in_resume():
    text, _ = apply_deterministic_corrections(
        RAW_STT,
        resume_terms=_ravi_terms(),
        candidate_name="Ravi Molake",
        job_position="Python Developer",
    )
    assert "I'm confident" in text
    assert "role aligns" in text.lower() or "happy to share" in text.lower()


def test_llm_path_skips_fact_injection(monkeypatch):
    """Even if LLM suggests resume facts, block expansions."""

    def fake_llm(*_args, **_kwargs):
        return {
            "corrections": [
                {
                    "from": "99 accuracy",
                    "to": "99.57% accuracy",
                    "reason": "resume metric",
                },
                {
                    "from": "Infinity Publication",
                    "to": "approved for publication",
                    "reason": "resume phrase",
                },
            ]
        }

    monkeypatch.setattr(
        "agents.interview_agent.stt_corrector.call_llama_json",
        fake_llm,
    )
    monkeypatch.setattr(
        "agents.interview_agent.stt_corrector.llama_available",
        lambda: True,
    )

    result = correct_transcript_with_resume(
        "The model achieves 99 accuracy and approved Infinity Publication.",
        context={"job_position": "Python Developer", "skills": "Python"},
        resume_terms=_ravi_terms(),
        candidate_name="Ravi Molake",
    )
    assert "99.57" not in result["text"]
    assert "Infinity Publication" in result["text"]


def test_whisper_prompt_is_natural_speech_not_instructions():
    prompt = build_whisper_prompt(
        ["FastAPI", "Tater-Check"],
        candidate_name="Ravi Laxman Molake",
    )
    assert prompt is not None
    lowered = prompt.lower()
    assert "speaker name" not in lowered
    assert "spell these resume terms" not in lowered
    assert "ravi laxman molake" in lowered


def test_strip_speaker_name_prompt_echo():
    cleaned = strip_whisper_artifacts(
        "Hello, my name is Ravi. Speaker name, Ravichandran, P.A. Inventory, A. L.A."
    )
    assert "speaker name" not in cleaned.lower()
