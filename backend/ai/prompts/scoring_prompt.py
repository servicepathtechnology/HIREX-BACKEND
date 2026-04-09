"""AI scoring prompt builder for HireX Part 4."""

SYSTEM_PROMPT = """You are an expert hiring evaluator for HireX, a skills-based hiring platform.
Your job is to evaluate a candidate's submission for a real hiring task.
You must be objective, specific, and rigorous. Base all scores strictly on
the submission content and the provided rubric. Do not consider writing style,
grammar, or presentation unless the task explicitly requires it.
Always respond with valid JSON only. No preamble, no explanation outside JSON."""

MAX_TEXT_TOKENS = 8000
MAX_CODE_TOKENS = 6000
CHARS_PER_TOKEN = 4  # rough estimate


def _truncate(content: str, max_tokens: int) -> str:
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[Content truncated due to length limit]"


def build_scoring_prompt(task: dict, submission: dict, criteria: list) -> str:
    """Build the user prompt for AI scoring."""
    criteria_text = "\n".join(
        f"- {c['name']} (Weight: {c.get('weight', 0)}%): {c.get('description', '')}"
        for c in criteria
    )

    # Determine submission content
    sub_type = submission.get("submission_types", "text")
    text_content = submission.get("text_content") or ""
    code_content = submission.get("code_content") or ""
    notes = submission.get("notes") or ""

    if code_content:
        content_section = f"Type: code\nLanguage: {submission.get('code_language', 'unknown')}\nContent:\n{_truncate(code_content, MAX_CODE_TOKENS)}"
    elif text_content:
        content_section = f"Type: text\nContent:\n{_truncate(text_content, MAX_TEXT_TOKENS)}"
    elif submission.get("link_url"):
        content_section = f"Type: link\nURL: {submission['link_url']}\n(AI cannot fetch external URLs — scoring based on notes and context only)"
    elif submission.get("file_urls"):
        content_section = f"Type: file submission\nFiles: {', '.join(submission['file_urls'])}\n(AI scores Approach criterion only based on metadata and notes)"
    else:
        content_section = "Type: unknown\nNo content provided."

    # Build criteria JSON structure for response
    criteria_json = "\n".join(
        f'    {{"criterion_name": "{c["name"]}", "score": <0-100>, "reasoning": "<2-3 sentences>", "improvement_suggestion": "<1 sentence>"}}'
        for c in criteria
    )

    return f"""TASK TITLE: {task.get('title', '')}
TASK DOMAIN: {task.get('domain', '')}
TASK DIFFICULTY: {task.get('difficulty', '')}

PROBLEM STATEMENT:
{task.get('problem_statement', '')}

EVALUATION RUBRIC:
{criteria_text}

CANDIDATE SUBMISSION:
{content_section}
Notes from candidate: {notes}

INSTRUCTIONS:
1. Score each criterion on a scale of 0 to 100.
2. Provide 2-3 sentences of specific reasoning for each score.
3. Provide one specific improvement suggestion per criterion.
4. Write a 3-sentence executive summary of this submission.
5. Flag if submission appears to be: (a) copied from another source,
   (b) primarily AI-generated without meaningful human contribution.

RESPOND ONLY WITH THIS JSON STRUCTURE:
{{
  "criteria_scores": [
{criteria_json}
  ],
  "total_score": <weighted average 0-100>,
  "executive_summary": "<3 sentences>",
  "plagiarism_suspected": <true|false>,
  "ai_generated_suspected": <true|false>,
  "flags_reasoning": "<explain any flags, or empty string>"
}}"""
