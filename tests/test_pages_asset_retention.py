"""Keep both sides of a Pages manifest handoff downloadable."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("manifest_read", ["true", "false"])
def test_cleanup_preserves_current_and_previous_deployed_archives(tmp_path, manifest_read):
    # Failed deployments can leave newer orphan archives ahead of the old live
    # archive. Retaining only the newest uploads can break a sync in flight.
    jobs = yaml.safe_load(Path(".github/workflows/pages.yml").read_text())["jobs"]
    script = jobs["prune-cli-data"]["steps"][0]["run"]
    names = [f"benchmark-radar-data-{n:012x}.zip" for n in range(6)]
    previous, current = names[0], names[-1]
    script = script.replace("${{ needs.publish-cli-data.outputs.asset-name }}", current)
    mock = tmp_path / "gh"
    mock.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "if sys.argv[1:3] == ['release', 'view']:\n"
        "    print(os.environ['ASSETS'])\n"
        "elif sys.argv[1:3] == ['release', 'delete-asset']:\n"
        "    with Path(os.environ['DELETED']).open('a') as f:\n"
        "        f.write(sys.argv[4] + '\\n')\n"
        "else:\n"
        "    raise SystemExit('unexpected gh command')\n"
    )
    mock.chmod(0o755)
    deleted = tmp_path / "deleted"
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", script],
        check=True,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "example/radar",
            "PREVIOUS_ASSET": previous,
            "MANIFEST_READ": manifest_read,
            "DELETED": str(deleted),
            "ASSETS": json.dumps(
                {"assets": [{"name": name, "createdAt": n} for n, name in enumerate(names)]}
            ),
        },
    )
    removed = deleted.read_text().splitlines() if deleted.exists() else []
    assert removed == ([names[1]] if manifest_read == "true" else [])
