"""Runtime prompt-style instructions selected in admin settings."""

from agents.screening_agent.config import settings


_STYLE_INSTRUCTIONS = {
    "detailed_analysis": "Capture all supported details and preserve evidence precisely.",
    "quick_summary": "Prioritize concise, high-confidence facts and avoid repetition.",
    "technical_focus": "Prioritize technical skills, tools, projects, and relevant experience.",
    "cultural_fit_focus": "Also preserve collaboration, leadership, communication, and teamwork evidence.",
}


def prompt_style_instruction() -> str:
    return _STYLE_INSTRUCTIONS.get(
        settings.SCREENING_PROMPT_STYLE,
        _STYLE_INSTRUCTIONS["detailed_analysis"],
    )
