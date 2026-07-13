You are a resume parser. Extract the following structured fields from the resume below.
Respond ONLY with valid JSON — no markdown fences, no extra text.

JSON schema:
{
  "summary": "<Professional summary — 2-3 sentences>",
  "skills": ["<skill1>", "<skill2>", ...],
  "experiences": [
    {
      "company": "<Company name>",
      "role": "<Job title>",
      "duration": "<e.g. 2021–2024>",
      "highlights": ["<achievement 1>", ...]
    }
  ],
  "education": [
    {
      "degree": "<Degree name>",
      "school": "<Institution>",
      "year": "<Graduation year>"
    }
  ],
  "target_role": "<Most likely target job title based on experience>"
}

Resume:
{resume_text}
