"""YouTube Data API client (feature-flagged) and the private-only publisher guard.

Safety design:
- `YouTubePublisher.upload()` has NO visibility parameter. It always sends privacyStatus
  "private" and verifies the API echoed "private" back.
- `YouTubePublisher.set_visibility()` is a separate operator action that requires the
  operator to retype the episode id as confirmation.
- Credentials/tokens are never printed or logged.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

PRIVATE = "private"
ALLOWED_VISIBILITY = {"private", "unlisted", "public", "scheduled"}
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]


class UnsafeVisibilityError(RuntimeError):
    pass


class YouTubeNotConfigured(RuntimeError):
    pass


class YouTubeClient(Protocol):
    def insert_video(self, video_path: Path, body: dict[str, Any],
                     thumbnail: Path | None) -> dict[str, Any]: ...

    def update_status(self, video_id: str, status: dict[str, Any]) -> dict[str, Any]: ...


class YouTubePublisher:
    def __init__(self, client: YouTubeClient):
        self.client = client

    def upload(self, video_path: Path, *, title: str, description: str, tags: list[str],
               category_id: str = "27", default_language: str = "en",
               contains_synthetic_media: bool | None = None,
               thumbnail: Path | None = None) -> dict[str, Any]:
        status: dict[str, Any] = {
            "privacyStatus": PRIVATE,
            "selfDeclaredMadeForKids": False,
        }
        if contains_synthetic_media is not None:
            status["containsSyntheticMedia"] = contains_synthetic_media
        body = {
            "snippet": {"title": title[:100], "description": description[:5000], "tags": tags,
                        "categoryId": category_id, "defaultLanguage": default_language},
            "status": status,
        }
        if body["status"]["privacyStatus"] != PRIVATE:  # defence in depth
            raise UnsafeVisibilityError("Upload must be private")
        result = self.client.insert_video(video_path, body, thumbnail)
        echoed = result.get("status", {}).get("privacyStatus")
        if echoed != PRIVATE:
            raise UnsafeVisibilityError(
                f"API returned privacyStatus={echoed!r}; expected 'private'. Check the video "
                "in YouTube Studio immediately."
            )
        return result

    def set_visibility(self, video_id: str, *, episode_id: str, confirm_episode_id: str,
                       visibility: str, publish_at: datetime | None = None) -> dict[str, Any]:
        if visibility not in ALLOWED_VISIBILITY:
            raise ValueError(f"visibility must be one of {sorted(ALLOWED_VISIBILITY)}")
        if confirm_episode_id != episode_id:
            raise UnsafeVisibilityError(
                "Visibility change refused: confirmation does not match the episode id."
            )
        if visibility == "scheduled":
            if publish_at is None:
                raise ValueError("Scheduling requires publish_at")
            status = {"privacyStatus": PRIVATE, "publishAt": publish_at.isoformat()}
        else:
            status = {"privacyStatus": visibility}
        return self.client.update_status(video_id, status)


class GoogleYouTubeClient:  # pragma: no cover - requires real OAuth credentials
    """Real client. Untested until the operator connects OAuth credentials."""

    def __init__(self, client_secrets: Path, token_file: Path):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise YouTubeNotConfigured(
                "Install the optional extra: uv sync --extra youtube"
            ) from exc
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
                creds = flow.run_local_server(port=0)
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json())
            token_file.chmod(0o600)
        self._yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def insert_video(self, video_path: Path, body: dict[str, Any],
                     thumbnail: Path | None) -> dict[str, Any]:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True,
                                mimetype="video/mp4")
        request = self._yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _status, response = request.next_chunk()
        if thumbnail and thumbnail.exists():
            self._yt.thumbnails().set(videoId=response["id"],
                                      media_body=MediaFileUpload(str(thumbnail))).execute()
        return response

    def update_status(self, video_id: str, status: dict[str, Any]) -> dict[str, Any]:
        return self._yt.videos().update(part="status",
                                        body={"id": video_id, "status": status}).execute()


def redact(obj: Any) -> str:
    """JSON dump with anything token-like removed (for logs)."""
    def scrub(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: ("***" if any(s in k.lower() for s in ("token", "secret", "key"))
                        else scrub(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [scrub(v) for v in o]
        return o
    return json.dumps(scrub(obj), default=str)
