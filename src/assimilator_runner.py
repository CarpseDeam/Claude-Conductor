#!/usr/bin/env python
"""Background assimilation runner.

Standalone script that runs codebase assimilation in a subprocess
and reports completion via TaskTracker.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    """Run assimilation and report result to TaskTracker."""
    if len(sys.argv) < 3:
        sys.exit(1)

    project_path = Path(sys.argv[1])
    task_id = sys.argv[2]

    if not project_path.exists():
        sys.exit(1)

    from assimilator.core import Assimilator
    from assimilator.output.cache import ManifestCache
    from tasks.tracker import TaskTracker

    tracker = TaskTracker()

    try:
        assimilator = Assimilator(project_path)
        manifest = assimilator.assimilate(force_refresh=True)

        cache = ManifestCache()
        cache.save(project_path, manifest)

        file_count = manifest.stats.get('files', 0)
        component_count = len(manifest.components)

        tracker.complete_task(
            task_id,
            files_modified=[],
            summary=f"Analyzed {file_count} files, {component_count} components"
        )
    except Exception as e:
        tracker.fail_task(task_id, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
