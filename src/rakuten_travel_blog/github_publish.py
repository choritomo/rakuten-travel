from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class PublishSummary:
    uploaded: int = 0
    skipped: int = 0
    deleted: int = 0


class GitHubPublishError(RuntimeError):
    pass


class GitHubContentsPublisher:
    def __init__(self, token: str, repository: str, branch: str = "main") -> None:
        if "/" not in repository:
            raise ValueError("Repository must be in the form owner/name.")
        owner, name = repository.split("/", 1)
        self.owner = owner
        self.name = name
        self.branch = branch
        self.token = token
        self.api_base = "https://api.github.com"

    def publish_directory(self, source_dir: Path, repo_prefix: str, commit_message: str) -> PublishSummary:
        if not source_dir.exists():
            raise GitHubPublishError(f"Source directory does not exist: {source_dir}")

        summary = PublishSummary()
        repo_prefix = repo_prefix.strip("/").replace("\\", "/")
        manifest_path = self._join_repo_path(repo_prefix, ".publish-manifest.json")
        previous_files = self._read_manifest(manifest_path)

        local_files: dict[str, bytes] = {}
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_dir).as_posix()
            repo_path = self._join_repo_path(repo_prefix, relative)
            local_files[repo_path] = path.read_bytes()

        for repo_path, content in local_files.items():
            changed = self.put_file(repo_path, content, commit_message)
            if changed:
                summary.uploaded += 1
            else:
                summary.skipped += 1

        current_files = sorted(local_files.keys())
        for stale_path in previous_files:
            if stale_path == manifest_path or stale_path in current_files:
                continue
            if self.delete_file(stale_path, commit_message):
                summary.deleted += 1

        manifest_payload = {
            "files": current_files + [manifest_path],
            "published_at": datetime.now(timezone.utc).isoformat(),
            "branch": self.branch,
        }
        if self.put_file(
            manifest_path,
            json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            commit_message,
        ):
            summary.uploaded += 1
        else:
            summary.skipped += 1

        return summary

    def put_file(self, repo_path: str, content: bytes, commit_message: str) -> bool:
        existing = self.get_file(repo_path)
        if existing is not None:
            existing_content = self._decode_content(existing)
            if existing_content == content:
                return False

        payload = {
            "message": commit_message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.branch,
        }
        if existing is not None and "sha" in existing:
            payload["sha"] = existing["sha"]
        self._request_json("PUT", self._contents_path(repo_path), payload)
        return True

    def delete_file(self, repo_path: str, commit_message: str) -> bool:
        existing = self.get_file(repo_path)
        if existing is None:
            return False
        payload = {
            "message": commit_message,
            "sha": existing["sha"],
            "branch": self.branch,
        }
        self._request_json("DELETE", self._contents_path(repo_path), payload)
        return True

    def get_file(self, repo_path: str) -> dict[str, object] | None:
        try:
            return self._request_json("GET", self._contents_path(repo_path, include_ref=True))
        except GitHubPublishError as exc:
            if "404" in str(exc):
                return None
            raise

    def _read_manifest(self, manifest_path: str) -> list[str]:
        payload = self.get_file(manifest_path)
        if payload is None:
            return []
        try:
            manifest = json.loads(self._decode_content(payload).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        files = manifest.get("files", [])
        if not isinstance(files, list):
            return []
        return [str(item) for item in files]

    def _decode_content(self, payload: dict[str, object]) -> bytes:
        content = str(payload.get("content", ""))
        encoding = str(payload.get("encoding", ""))
        if encoding != "base64":
            raise GitHubPublishError("Unexpected GitHub content encoding.")
        normalized = content.replace("\n", "")
        return base64.b64decode(normalized.encode("ascii"))

    def _contents_path(self, repo_path: str, include_ref: bool = False) -> str:
        encoded_path = quote(repo_path.strip("/"), safe="/")
        path = f"/repos/{quote(self.owner)}/{quote(self.name)}/contents/{encoded_path}"
        if include_ref:
            path += f"?ref={quote(self.branch)}"
        return path

    def _request_json(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.api_base + path,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "rakuten-travel-site-publisher/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubPublishError(f"GitHub API request failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise GitHubPublishError(f"GitHub API request failed: {exc.reason}") from exc

        if not raw:
            return {}
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        raise GitHubPublishError("Unexpected GitHub API response.")

    @staticmethod
    def _join_repo_path(prefix: str, relative_path: str) -> str:
        relative_path = relative_path.strip("/").replace("\\", "/")
        if not prefix:
            return relative_path
        return f"{prefix}/{relative_path}" if relative_path else prefix
