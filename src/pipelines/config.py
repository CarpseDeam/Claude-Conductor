"""Pipeline configuration management."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

AUTO_DOCS_PROMPT = '''You are a documentation maintainer. Review this git diff and update CLAUDE.md in the project root.

DIFF:
{diff}

TARGET FILE: CLAUDE.md (project root)

RULES:
1. Add a changelog entry at the top of the "## Changelog" section
   Format: "- type: description" (feat/fix/refactor/docs)

2. Update any outdated component or structure information based on the diff

3. Be surgical - only modify sections that need updating

4. Keep tone professional and concise

5. After updating, commit with message: "docs: [brief description]"

If the diff only touches CLAUDE.md, skip to avoid recursive updates.
'''


@dataclass
class PipelineStep:
    name: str
    agent: str
    model: str
    task_template: str
    enabled: bool = True
    include_diff: bool = True
    condition: dict = field(default_factory=dict)


@dataclass
class PipelineConfig:
    post_commit: list[PipelineStep] = field(default_factory=list)

    @classmethod
    def load(cls, project_path: Path) -> "PipelineConfig":
        config_path = project_path / ".conductor" / "pipelines.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            return cls._from_dict(data)
        return cls._default()

    @classmethod
    def _default(cls) -> "PipelineConfig":
        return cls(
            post_commit=[
                PipelineStep(
                    name="auto_docs",
                    agent="gemini",
                    model="gemini-2.5-flash",
                    task_template=AUTO_DOCS_PROMPT,
                    enabled=True,
                    include_diff=True
                )
            ]
        )

    @classmethod
    def _from_dict(cls, data: dict) -> "PipelineConfig":
        steps = []
        for step_data in data.get("post_commit", []):
            steps.append(PipelineStep(**step_data))
        return cls(post_commit=steps)

    def save(self, project_path: Path) -> None:
        config_dir = project_path / ".conductor"
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "pipelines.json"

        data = {
            "post_commit": [asdict(step) for step in self.post_commit]
        }
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
