from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rakuten_travel_blog.github_publish import GitHubContentsPublisher
from rakuten_travel_blog.runtime_env import load_env_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the local Rakuten Travel site and publish the generated files to GitHub Pages."
    )
    parser.add_argument("--output-dir", default="dist", help="Local output directory used for the build.")
    parser.add_argument("--repo-prefix", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--sample-data", action="store_true", help="Build with sample data instead of live API data.")
    parser.add_argument("--build-only", action="store_true", help="Build the site locally but skip GitHub upload.")
    return parser.parse_args()


def main() -> int:
    load_env_file(ROOT / ".env")
    args = parse_args()
    if not args.repo_prefix:
        args.repo_prefix = os.getenv("GITHUB_PAGES_DIR", "site")
    if not args.branch:
        args.branch = os.getenv("GITHUB_BRANCH", "main")

    build_command = [sys.executable, str(ROOT / "scripts" / "generate_site.py"), "--output-dir", args.output_dir]
    if args.sample_data:
        build_command.append("--sample-data")

    build_result = subprocess.run(
        build_command,
        cwd=ROOT,
        capture_output=True,
    )
    stderr_text = build_result.stderr.decode("utf-8", errors="replace").strip()
    if build_result.returncode != 0:
        if stderr_text:
            emit_text(stderr_text, stream=sys.stderr)
        return build_result.returncode

    if args.build_only:
        return 0

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not repository or not token:
        print(
            json.dumps(
                {
                    "error": "GITHUB_REPOSITORY と GITHUB_TOKEN が必要です。",
                    "hint": "GitHubへの自動公開をしないなら --build-only を使ってください。",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 4

    publisher = GitHubContentsPublisher(token=token, repository=repository, branch=args.branch)
    jst = timezone(timedelta(hours=9), name="JST")
    commit_message = f"Update travel site ({datetime.now(jst).strftime('%Y-%m-%d %H:%M JST')})"
    summary = publisher.publish_directory(
        source_dir=(ROOT / args.output_dir).resolve(),
        repo_prefix=args.repo_prefix,
        commit_message=commit_message,
    )
    print(
        json.dumps(
            {
                "repository": repository,
                "branch": args.branch,
                "repo_prefix": args.repo_prefix,
                "uploaded": summary.uploaded,
                "skipped": summary.skipped,
                "deleted": summary.deleted,
            },
            ensure_ascii=False,
        )
    )
    return 0


def emit_text(text: str, stream: object = sys.stdout) -> None:
    target = stream if hasattr(stream, "write") else sys.stdout
    encoding = getattr(target, "encoding", None) or "utf-8"
    safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(safe, file=target)


if __name__ == "__main__":
    raise SystemExit(main())
