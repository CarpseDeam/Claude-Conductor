import httpx

from .contracts import GitDiff


class CommitMessageGenerator:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "mistral:latest"
    TIMEOUT = 30

    SYSTEM_PROMPT = """You are a git commit message generator. Generate a commit message in conventional commit format.

Format: type(scope): description

Types: feat, fix, refactor, docs, style, test, chore

Rules:
- Maximum 72 characters total
- Use imperative mood (add, fix, update, not added, fixed, updated)
- Be concise and specific
- Return ONLY the commit message, nothing else"""

    def generate(self, diff: GitDiff) -> str:
        prompt = f"""{self.SYSTEM_PROMPT}

Generate a commit message for this diff:

Files changed: {', '.join(diff.files_changed)}

Diff content:
{diff.content[:4000]}"""

        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 100,
                "temperature": 0.3
            }
        }

        with httpx.Client(timeout=self.TIMEOUT) as client:
            response = client.post(self.OLLAMA_URL, json=payload)
            response.raise_for_status()

        data = response.json()
        raw_response = data.get("response", "").strip()

        commit_msg = raw_response.split('\n')[0].strip()
        commit_msg = commit_msg.strip('"\'')

        if len(commit_msg) > 72:
            commit_msg = commit_msg[:69] + "..."

        return commit_msg
