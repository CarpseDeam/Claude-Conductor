"""GUI viewer entry point. Launched as subprocess by server.py."""
import sys
import traceback
from pathlib import Path

# Log errors to file since stdout/stderr are piped to DEVNULL
_LOG_FILE = Path(__file__).parent / "_gui_error.log"


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: gui_viewer.py <project_path> <prompt_file> [--add-dir <path>]... "
              "[--cli claude|gemini|codex] [--model <model>] [--git-branch <n>] "
              "[--godot-project <path>] [--task-id <id>]")
        sys.exit(1)

    project_path = sys.argv[1]
    prompt_file = sys.argv[2]

    additional_dirs = []
    cli = "claude"
    model = None
    git_branch = None
    godot_project = None
    task_id = None

    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--add-dir" and i + 1 < len(sys.argv):
            additional_dirs.append(sys.argv[i + 1])
            i += 2
        elif arg == "--cli" and i + 1 < len(sys.argv):
            cli = sys.argv[i + 1]
            i += 2
        elif arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
            i += 2
        elif arg == "--git-branch" and i + 1 < len(sys.argv):
            git_branch = sys.argv[i + 1]
            i += 2
        elif arg == "--godot-project" and i + 1 < len(sys.argv):
            godot_project = sys.argv[i + 1]
            i += 2
        elif arg == "--task-id" and i + 1 < len(sys.argv):
            task_id = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    prompt = Path(prompt_file).read_text(encoding="utf-8")

    from gui.viewer import ClaudeOutputWindow
    window = ClaudeOutputWindow(
        project_path, prompt, additional_dirs, prompt_file,
        cli, model, git_branch, godot_project, task_id,
    )
    window.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open(_LOG_FILE, "w") as f:
            f.write(f"Python: {sys.executable}\n")
            f.write(f"Version: {sys.version}\n")
            f.write(f"Args: {sys.argv}\n\n")
            f.write(f"ERROR: {e}\n\n")
            f.write(traceback.format_exc())
        raise
