const resumeFile = document.querySelector("#resumeFile");
const fileLabel = document.querySelector("#fileLabel");
const jdFile = document.querySelector("#jdFile");
const jdFileLabel = document.querySelector("#jdFileLabel");
const jdText = document.querySelector("#jdText");
const evaluateBtn = document.querySelector("#evaluateBtn");
const statusText = document.querySelector("#statusText");
const results = document.querySelector("#results");
const docsLink = document.querySelector("#docsLink");

// When the UI is served by FastAPI (/ui/), use the same origin.
// When opened using Live Server, Vite, or file://, use the local API.
const API_BASE = (() => {
  const explicit = document
    .querySelector('meta[name="api-base-url"]')
    ?.content?.trim();

  if (explicit) {
    return explicit.replace(/\/$/, "");
  }

  if (
    (window.location.protocol === "http:" ||
      window.location.protocol === "https:") &&
    window.location.pathname.startsWith("/ui")
  ) {
    return window.location.origin;
  }

  return "http://127.0.0.1:8030";
})();

if (docsLink) {
  docsLink.href = `${API_BASE}/docs`;
}

resumeFile.addEventListener("change", () => {
  fileLabel.textContent =
    resumeFile.files[0]?.name || "Choose a PDF or DOCX resume";
});

jdFile.addEventListener("change", () => {
  jdFileLabel.textContent =
    jdFile.files[0]?.name || "Upload a PDF or DOCX JD (optional)";
});

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.style.color = isError ? "#b42318" : "#667085";
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function addChips(containerId, values, missing = false) {
  const container = document.querySelector(containerId);

  if (!container) {
    return;
  }

  container.replaceChildren();

  const valueArray = asArray(values);
  const items = valueArray.length ? valueArray : ["None"];

  items.forEach((value) => {
    const chip = document.createElement("span");

    chip.className = `chip${missing ? " missing" : ""}`;
    chip.textContent = String(value);

    container.appendChild(chip);
  });
}

function addList(containerId, values) {
  const container = document.querySelector(containerId);

  if (!container) {
    return;
  }

  container.replaceChildren();

  const valueArray = asArray(values);

  const items = valueArray.length
    ? valueArray
    : ["No items identified."];

  items.forEach((value) => {
    const item = document.createElement("li");

    item.textContent = String(value);

    container.appendChild(item);
  });
}

/**
 * Removes invalid candidate-name values.
 *
 * Examples rejected:
 *
 * <!-- image -->
 * ![image](...)
 * [image]
 * <img>
 * image
 * logo
 * unknown
 * null
 */
function collapseSpacedLetterName(line) {
  const cleaned = String(line || "")
    .replace(/^#+\s*/, "")
    .trim();

  if (!cleaned) {
    return "";
  }

  const parts = cleaned.split(/\s{2,}/).map((chunk) => chunk.trim()).filter(Boolean);
  const nameParts = [];

  for (const chunk of parts.length ? parts : [cleaned]) {
    const tokens = chunk.split(/\s+/).filter(Boolean);

    if (tokens.length && tokens.every((token) => token.length === 1 && /[A-Za-z]/.test(token))) {
      if (tokens.length < 2) {
        continue;
      }
      nameParts.push(
        (() => {
          const joined = tokens.join("");
          return joined.charAt(0).toUpperCase() + joined.slice(1).toLowerCase();
        })()
      );
      continue;
    }

    if (tokens.length >= 1 && tokens.length <= 4) {
      nameParts.push(
        ...tokens.map(
          (token) => token.charAt(0).toUpperCase() + token.slice(1).toLowerCase()
        )
      );
    }
  }

  const result = nameParts.join(" ").trim();
  return result.length >= 3 && result.length <= 80 ? result : "";
}

function cleanCandidateName(value) {
  const name = String(value ?? "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!name) {
    return "";
  }

  const spacedName = collapseSpacedLetterName(name);
  if (spacedName) {
    return spacedName;
  }

  const normalized = name.toLowerCase();

  const invalidExactValues = new Set([
    "candidate",
    "candidate name",
    "unknown",
    "not specified",
    "not available",
    "n/a",
    "na",
    "null",
    "none",
    "image",
    "img",
    "picture",
    "photo",
    "figure",
    "logo",
  ]);

  if (invalidExactValues.has(normalized)) {
    return "";
  }

  // Reject HTML comments such as <!-- image -->.
  if (/^<!--\s*.*?\s*-->$/i.test(name)) {
    return "";
  }

  // Reject Markdown images such as ![image](path).
  if (/^!\[[^\]]*\]\([^)]*\)$/i.test(name)) {
    return "";
  }

  // Reject plain image placeholders.
  if (
    /^\[?(?:image|img|picture|photo|figure|logo)\]?$/i.test(name)
  ) {
    return "";
  }

  // Reject HTML image tags.
  if (/^<(?:image|img)(?:\s[^>]*)?\/?\s*>$/i.test(name)) {
    return "";
  }

  // A candidate name should not be an email address.
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(name)) {
    return "";
  }

  // A candidate name should not be a URL.
  if (/^(?:https?:\/\/|www\.)/i.test(name)) {
    return "";
  }

  // A candidate name should not be only a phone number.
  if (/^[+()\d\s-]{7,}$/.test(name)) {
    return "";
  }

  return name;
}

/**
 * Looks for the candidate name in common structured-resume fields.
 */
function findNameInParsedResume(parsedResume) {
  if (!parsedResume || typeof parsedResume !== "object") {
    return "";
  }

  const possibleNames = [
    parsedResume.name,
    parsedResume.full_name,
    parsedResume.candidate_name,
    parsedResume.candidateName,

    parsedResume.personal_details?.name,
    parsedResume.personalDetails?.name,

    parsedResume.personal_information?.name,
    parsedResume.personalInformation?.name,

    parsedResume.contact_information?.name,
    parsedResume.contactInformation?.name,

    parsedResume.contact_info?.name,
    parsedResume.contactInfo?.name,

    parsedResume.basic_info?.name,
    parsedResume.basicInfo?.name,

    parsedResume.basics?.name,
    parsedResume.header?.name,
    parsedResume.profile?.name,
  ];

  for (const value of possibleNames) {
    const cleanedName = cleanCandidateName(value);

    if (cleanedName) {
      return cleanedName;
    }
  }

  return "";
}

/**
 * Tries to find the candidate name from the first lines of the
 * extracted resume text when the structured parser missed the name.
 */
function findNameInExtractedText(extraction) {
  const parsedResume = extraction?.parsed_data || {};

  const possibleTexts = [
    extraction?.full_text,
    extraction?.raw_text,
    extraction?.extracted_text,
    extraction?.text,

    parsedResume?.source_text,
    parsedResume?.full_text,
    parsedResume?.raw_text,
    parsedResume?.extracted_text,
    parsedResume?.text,
  ];

  const rawText = possibleTexts.find(
    (value) => typeof value === "string" && value.trim()
  );

  if (!rawText) {
    return "";
  }

  const sectionHeadings = new Set([
    "career objective",
    "professional summary",
    "professional profile",
    "summary",
    "profile",
    "key skills",
    "technical skills",
    "skills",
    "experience",
    "work experience",
    "professional experience",
    "education",
    "academic projects",
    "projects",
    "certifications",
    "achievements",
  ]);

  const lines = rawText
    .split(/\r?\n/)
    .map((line) => {
      const withoutMarkdownHeading = line.replace(/^#+\s*/, "");

      return cleanCandidateName(withoutMarkdownHeading);
    })
    .filter(Boolean)
    .slice(0, 15);

  for (const line of lines) {
    const normalized = line
      .toLowerCase()
      .replace(/[:\s]+$/, "");

    if (sectionHeadings.has(normalized)) {
      continue;
    }

    if (/linkedin|github|portfolio/i.test(line)) {
      continue;
    }

    if (line.length < 3 || line.length > 80) {
      continue;
    }

    // Candidate names generally contain letters, spaces,
    // apostrophes, periods, or hyphens.
    if (/^[\p{L}][\p{L}\s.'-]+$/u.test(line)) {
      return line;
    }
  }

  return "";
}

/**
 * Candidate-name priority:
 *
 * 1. Candidate name returned by evaluation API
 * 2. Name from structured parsed resume
 * 3. Name from extracted resume text
 */
function resolveCandidateName(candidate, extraction) {
  const evaluationName = cleanCandidateName(
    candidate?.name ||
      candidate?.full_name ||
      candidate?.candidate_name
  );

  if (evaluationName) {
    return evaluationName;
  }

  const parsedResumeName = findNameInParsedResume(
    extraction?.parsed_data
  );

  if (parsedResumeName) {
    return parsedResumeName;
  }

  return findNameInExtractedText(extraction);
}


function formatYears(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "Not verified";
  }

  const years = Number(value);
  return `${years.toFixed(years % 1 === 0 ? 0 : 2)} years`;
}

function formatJdExperience(jd) {
  const minimum = jd?.minimum_experience_years;
  const maximum = jd?.maximum_experience_years;
  const preferred = jd?.preferred_experience_years;

  if (minimum != null && maximum != null) {
    return `${minimum}–${maximum} years required`;
  }

  if (minimum != null) {
    return `At least ${minimum} years required`;
  }

  if (preferred != null) {
    return `${preferred} years preferred`;
  }

  return "Not specified";
}

function formatExperienceEntry(entry) {
  const role = String(entry?.role || "Unspecified role");
  const company = entry?.company ? ` at ${entry.company}` : "";
  const dateRange = entry?.date_range ? ` (${entry.date_range})` : "";
  const duration =
    entry?.duration_years == null
      ? ""
      : ` — ${formatYears(entry.duration_years)}`;
  const reason = entry?.reason ? `: ${entry.reason}` : "";

  return `${role}${company}${dateRange}${duration}${reason}`;
}

function renderBreakdown(score) {
  const weights = score?.score_weights || {};

  const metrics = [
    [
      "Required skills",
      score?.required_skill_score,
      weights.required_skills,
    ],
    [
      "Preferred skills",
      score?.preferred_skill_score,
      weights.preferred_skills,
    ],
    [
      "Experience",
      score?.experience_score,
      weights.experience,
    ],
    [
      "Education",
      score?.education_score,
      weights.education_certification,
    ],
    [
      "Keywords",
      score?.keyword_score,
      weights.keywords,
    ],
  ];

  const container = document.querySelector("#scoreBreakdown");

  if (!container) {
    return;
  }

  container.replaceChildren();

  metrics.forEach(([label, value, maximum]) => {
    const card = document.createElement("div");
    card.className = "metric";

    const number = document.createElement("strong");

    number.textContent =
      `${Number(value ?? 0).toFixed(1)}/` +
      `${Number(maximum ?? 0)}`;

    const caption = document.createElement("span");
    caption.textContent = label;

    card.append(number, caption);
    container.appendChild(card);
  });
}

function renderEvaluation(data, extraction) {
  const score = data?.score_breakdown || {};
  const jd = data?.extracted_jd_requirements || {};
  const match = data?.match_analysis || {};
  const candidate = data?.candidate_details || {};

  document.querySelector("#scoreValue").textContent =
    Math.round(Number(score.overall_score ?? 0));

  const badge = document.querySelector("#decisionBadge");

  const shortlistStatus =
    data?.shortlist_status || "Not decided";

  badge.textContent = shortlistStatus;
  badge.className = "badge";

  if (shortlistStatus === "Shortlisted") {
    badge.classList.add("shortlisted");
  }

  if (shortlistStatus === "Rejected") {
    badge.classList.add("rejected");
  }

  /*
   * Candidate-name fix:
   *
   * Do not display <!-- image -->.
   * Try evaluation data, parsed resume data, and extracted text.
   */
  const candidateName = resolveCandidateName(
    candidate,
    extraction
  );

  document.querySelector("#candidateName").textContent =
    candidateName || "Candidate";

  const emails = asArray(candidate.emails);
  const phones = asArray(candidate.phones);
  const links = asArray(candidate.links);

  document.querySelector("#candidateContact").textContent = [
    ...emails,
    ...phones,
    ...links,
  ]
    .filter(Boolean)
    .join(" · ");

  document.querySelector("#recommendation").textContent =
    data?.final_recommendation ||
    "No recommendation available.";

  const experience =
    data?.experience_assessment ||
    score?.experience_assessment ||
    {};

  document.querySelector("#experienceRequirement").textContent =
    experience.jd_requirement || "Not specified";

  document.querySelector("#totalExperience").textContent =
    formatYears(experience.candidate_total_experience_years);

  document.querySelector("#relevantExperience").textContent =
    formatYears(experience.candidate_relevant_experience_years);

  document.querySelector("#experienceResult").textContent =
    experience.result || "No experience result available.";

  addList(
    "#countedExperience",
    asArray(experience.counted_experience).map(formatExperienceEntry)
  );

  addList(
    "#excludedExperience",
    asArray(experience.excluded_experience).map(formatExperienceEntry)
  );

  document.querySelector("#jobTitle").textContent =
    jd.job_title || "Not specified";

  document.querySelector("#minimumExperience").textContent =
    formatJdExperience(jd);

  document.querySelector("#requiredRatio").textContent =
    `${Math.round(
      Number(match.required_match_ratio ?? 0) * 100
    )}%`;

  document.querySelector("#preferredRatio").textContent =
    `${Math.round(
      Number(match.preferred_match_ratio ?? 0) * 100
    )}%`;

  renderBreakdown(score);

  addChips(
    "#matchedSkills",
    score.matched_skills
  );

  addChips(
    "#missingSkills",
    score.missing_skills,
    true
  );

  addList(
    "#strengths",
    score.strengths
  );

  addList(
    "#concerns",
    score.concerns
  );

  const schedulingPanel = document.querySelector("#schedulingPanel");
  if (schedulingPanel) {
    schedulingPanel.classList.add("hidden");
  }

  results.classList.remove("hidden");

  results.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

async function readError(response) {
  try {
    const body = await response.json();

    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item) => item.msg)
        .join("; ");
    }

    return (
      body.detail ||
      `Request failed with HTTP ${response.status}.`
    );
  } catch {
    return `Request failed with HTTP ${response.status}.`;
  }
}

async function apiFetch(path, options, timeoutMs) {
  const controller = new AbortController();

  const timeout = window.setTimeout(
    () => controller.abort(),
    timeoutMs
  );

  try {
    return await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "The backend took too long to respond. " +
          "Check the PowerShell server log."
      );
    }

    throw new Error(
      `Cannot reach the backend at ${API_BASE}. ` +
        `Confirm Uvicorn is running, then open ` +
        `${API_BASE}/health.`
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

evaluateBtn.addEventListener("click", async () => {
  const file = resumeFile.files[0];
  const jd = jdText.value.trim();
  const jdDocument = jdFile.files[0];

  if (!file) {
    setStatus("Choose a resume first.", true);
    return;
  }

  if (!jd && !jdDocument) {
    setStatus("Upload or paste a job description first.", true);
    return;
  }

  evaluateBtn.disabled = true;
  results.classList.add("hidden");

  try {
    setStatus(
      "Parsing resume. " +
        "The first OCR run can take several minutes..."
    );

    const form = new FormData();
    form.append("file", file);

    const extractResponse = await apiFetch(
      "/extract",
      {
        method: "POST",
        body: form,
      },
      10 * 60 * 1000
    );

    if (!extractResponse.ok) {
      throw new Error(
        await readError(extractResponse)
      );
    }

    const extraction = await extractResponse.json();

    let jdPayload = null;

    if (jdDocument) {
      setStatus("Parsing job description document...");

      const jdForm = new FormData();
      jdForm.append("file", jdDocument);

      const jdUploadResponse = await apiFetch(
        "/api/jd/upload",
        {
          method: "POST",
          body: jdForm,
        },
        10 * 60 * 1000
      );

      if (!jdUploadResponse.ok) {
        throw new Error(await readError(jdUploadResponse));
      }

      jdPayload = await jdUploadResponse.json();

      if (!jd) {
        jdText.value = jdPayload.jd_text || "";
      }
    }

    setStatus(
      "Matching candidate to job description..."
    );

    const enqueueResponse = await apiFetch(
      "/api/candidates/evaluate/async",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          parsed_resume: extraction.parsed_data,
          ...(jdPayload
            ? {
                parsed_jd: jdPayload.parsed_jd,
                jd_source_text: jdPayload.jd_text,
                jd_original_filename: jdPayload.original_filename,
                jd_file_url: jdPayload.stored_file_url,
              }
            : {
                jd_text: jd,
              }),
          resume_original_filename: extraction.original_filename,
          resume_file_url: extraction.stored_file_url,
        }),
      },
      60 * 1000
    );

    if (!enqueueResponse.ok) {
      throw new Error(await readError(enqueueResponse));
    }

    const queued = await enqueueResponse.json();
    const pollUrl = queued.poll_url || `/api/candidates/evaluate/jobs/${queued.job_id}`;

    setStatus("Evaluation queued. Waiting for results...");

    const pollIntervalMs = 2000;
    const pollTimeoutMs = 15 * 60 * 1000;
    const pollStarted = Date.now();
    let evaluation = null;

    while (Date.now() - pollStarted < pollTimeoutMs) {
      const jobResponse = await apiFetch(pollUrl, { method: "GET" }, 60 * 1000);

      if (!jobResponse.ok) {
        throw new Error(await readError(jobResponse));
      }

      const job = await jobResponse.json();

      if (job.status === "completed") {
        evaluation = job.result;
        break;
      }

      if (job.status === "failed") {
        throw new Error(job.error || "Evaluation job failed.");
      }

      const queueHint =
        job.status === "pending"
          ? "Waiting in queue..."
          : "Processing evaluation...";
      setStatus(queueHint);
      await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
    }

    if (!evaluation) {
      throw new Error(
        "Evaluation timed out while waiting in the queue. Try again later."
      );
    }

    /*
     * Pass extraction to renderEvaluation so it can use
     * parsed resume data as a candidate-name fallback.
     */
    renderEvaluation(
      evaluation,
      extraction
    );

    if (evaluation.scheduling) {
      setStatus(
        "Evaluation complete. Shortlisted — interview invite sent automatically."
      );
    } else if (evaluation.persist_warning) {
      setStatus(
        `Evaluation complete. ${evaluation.persist_warning} Open HR Candidates to review.`,
        false
      );
    } else {
      setStatus("Evaluation complete. Candidate saved to HR review.");
    }
  } catch (error) {
    setStatus(
      error.message || "Evaluation failed.",
      true
    );
  } finally {
    evaluateBtn.disabled = false;
  }
});