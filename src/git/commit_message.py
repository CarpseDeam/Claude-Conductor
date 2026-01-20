import os

import httpx

from .contracts import GitDiff


class CommitMessageGenerator:
    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-3-5-haiku-latest"
    TIMEOUT = 30

    SYSTEM_PROMPT = """You are a git commit message generator. Generate a commit message in conventional commit format.

Format: type(scope): description

Types: feat, fix, refactor, docs, style, test, chore

Rules:
- Maximum 72 characters total
- Use imperative mood (add, fix, update, not added, fixed, updated)
- Be concise and specific
- Return ONLY the commit message, nothing else"""

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    def generate(self, diff: GitDiff) -> str:
        user_prompt = f"""Generate a commit message for this diff:

Files changed: {', '.join(diff.files_changed)}

Diff content:
{diff.content[:4000]}"""

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.MODEL,
            "max_tokens": 100,
            "system": self.SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        with httpx.Client(timeout=self.TIMEOUT) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        return data["content"][0]["text"].strip()
