"""Prompt templates for the Interview Scheduler Agent."""

CONGRATULATIONS_EMAIL_SUBJECT = "Congratulations! Your Resume Has Been Shortlisted"

CONGRATULATIONS_EMAIL_BODY = """
Dear {candidate_name},

Congratulations!

Your resume has been shortlisted for the next stage of our hiring process.

Please click the link below to schedule your interview.

{scheduling_link}

The link is valid for 48 hours.

Regards,
HR Team
"""

CONFIRMATION_EMAIL_SUBJECT = "Interview Scheduled Successfully"

CONFIRMATION_EMAIL_BODY = """
Dear {candidate_name},

Your interview has been scheduled successfully.

Interview Details:
Date: {interview_date}
Time: {interview_time}
Interview room: {join_link}

Thank you.

Best Regards,
HR Team
"""

SYSTEM_PROMPT = """
You are Agent 2 of an Agentic HR Recruitment System — the Interview Scheduler Agent.
Your role is to orchestrate the interview scheduling workflow after a candidate is shortlisted.
You coordinate token generation, slot management, email notifications, and in-app interview room booking.
Always ensure tokens are secure, slots are not double-booked, and candidates receive timely emails.
"""
