"""Talking to YouTube: sign in once, then upload a video, its thumbnail, captions and playlist.

The real client uses the YouTube Data API v3 with the token `kiddy auth youtube` saves in
secrets/. FakeYouTube records the calls instead, for --fake runs and the tests. What to upload and
when lives in kiddy.approval.publish.
"""

import itertools
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Protocol

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel, Field

from kiddy.state import YouTubeMetadata

CLIENT_FILE = "client_secret.json"  # downloaded from Google Cloud: a "Desktop app" OAuth client
TOKEN_FILE = "youtube_token.json"  # written by `kiddy auth youtube`
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]  # force-ssl: captions, playlists
RETRIES = 5  # for 5xx and rate-limit answers, with exponential backoff
CHUNK = 8 * 1024 * 1024
LEAD = timedelta(hours=1)  # YouTube needs time to process a video before it goes public
LANGUAGE_NAMES = {"en": "English"}  # the caption track's name in the player


class YouTubeError(Exception):
    """YouTube refused or failed a call. The message says why, in plain words."""


class Progress(BaseModel):
    """youtube.json in the episode folder: what is already on YouTube, so nothing runs twice."""

    video_id: str = ""
    publish_at: str = ""  # when it goes public (ISO time); empty: it stays private
    thumbnail: bool = False
    captions: bool = False
    playlist: bool = False
    warnings: list[str] = Field(default_factory=list)


class YouTube(Protocol):
    def upload(self, video: Path, body: dict) -> str: ...
    def set_thumbnail(self, video_id: str, image: Path) -> None: ...
    def add_captions(self, video_id: str, srt: Path, language: str) -> None: ...
    def add_to_playlist(self, video_id: str, title: str) -> None: ...


def sign_in(secrets_dir: Path) -> Path:
    """Open the browser once to sign in; save a refresh token so nothing asks again."""
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_dir / CLIENT_FILE), SCOPES)
    # select_account: pick the right Google account; consent: always get a refresh token back.
    credentials = flow.run_local_server(port=0, prompt="select_account consent")
    token = secrets_dir / TOKEN_FILE
    token.write_text(credentials.to_json(), encoding="utf-8")
    return token


class YouTubeClient:
    """The real YouTube Data API v3. Signs in from the saved token on its first call."""

    def __init__(self, secrets_dir: Path):
        self.secrets_dir = secrets_dir
        self._api = None

    @property
    def api(self):
        if self._api is None:
            token = self.secrets_dir / TOKEN_FILE
            if not token.exists():
                raise YouTubeError("not signed in to YouTube. Run: uv run kiddy auth youtube")
            credentials = Credentials.from_authorized_user_file(str(token), SCOPES)
            self._api = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        return self._api

    def channel_title(self) -> str:
        found = run(self.api.channels().list(part="snippet", mine=True))
        return found["items"][0]["snippet"]["title"] if found.get("items") else "(no channel)"

    def upload(self, video: Path, body: dict) -> str:
        media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=CHUNK, resumable=True)
        request = self.api.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        with plain_errors():
            while response is None:  # a stopped chunk is retried, not the whole file
                _, response = request.next_chunk(num_retries=RETRIES)
        return response["id"]

    def set_thumbnail(self, video_id: str, image: Path) -> None:
        media = MediaFileUpload(str(image), mimetype="image/jpeg")
        run(self.api.thumbnails().set(videoId=video_id, media_body=media))

    def add_captions(self, video_id: str, srt: Path, language: str) -> None:
        snippet = {"videoId": video_id, "language": language,
                   "name": LANGUAGE_NAMES.get(language, language), "isDraft": False}
        media = MediaFileUpload(str(srt), mimetype="application/octet-stream")
        run(self.api.captions().insert(part="snippet", body={"snippet": snippet},
                                       media_body=media))

    def add_to_playlist(self, video_id: str, title: str) -> None:
        snippet = {"playlistId": self._playlist(title),
                   "resourceId": {"kind": "youtube#video", "videoId": video_id}}
        run(self.api.playlistItems().insert(part="snippet", body={"snippet": snippet}))

    def _playlist(self, title: str) -> str:
        """The channel's playlist with this title, made the first time it's needed."""
        page: dict = {}
        while True:
            found = run(self.api.playlists().list(part="snippet", mine=True, maxResults=50,
                                                  **page))
            for item in found.get("items", []):
                if item["snippet"]["title"] == title:
                    return item["id"]
            if "nextPageToken" not in found:
                break
            page = {"pageToken": found["nextPageToken"]}
        body = {"snippet": {"title": title}, "status": {"privacyStatus": "public"}}
        return run(self.api.playlists().insert(part="snippet,status", body=body))["id"]


class FakeYouTube:
    """Records every call instead of uploading: offline and free. `fail` makes steps fail."""

    def __init__(self):
        self.calls: list[tuple[str, object]] = []
        self.fail: set[str] = set()

    def upload(self, video: Path, body: dict) -> str:
        self._record("upload", body)
        return f"fake{sum(name == 'upload' for name, _ in self.calls)}"

    def set_thumbnail(self, video_id: str, image: Path) -> None:
        self._record("thumbnail", video_id)

    def add_captions(self, video_id: str, srt: Path, language: str) -> None:
        self._record("captions", srt.read_text("utf-8"))

    def add_to_playlist(self, video_id: str, title: str) -> None:
        self._record("playlist", title)

    def _record(self, name: str, detail: object) -> None:
        if name in self.fail:
            raise YouTubeError(f"fake {name} failure")
        self.calls.append((name, detail))


def make_youtube(fake: bool, secrets_dir: Path) -> YouTube:
    return FakeYouTube() if fake else YouTubeClient(secrets_dir)


class plain_errors:
    """Turn Google's errors into a YouTubeError that says what to do."""

    def __enter__(self):
        return self

    def __exit__(self, kind, error, trace):
        if isinstance(error, RefreshError):
            raise YouTubeError("the YouTube sign-in expired or was removed. "
                               "Run: uv run kiddy auth youtube") from error
        if isinstance(error, HttpError):
            raise YouTubeError(explain(error)) from error
        return False


def run(request) -> dict:
    with plain_errors():
        return request.execute(num_retries=RETRIES)


def explain(error: HttpError) -> str:
    details = error.error_details if isinstance(error.error_details, list) else []
    reasons = {detail.get("reason") for detail in details if isinstance(detail, dict)}
    if reasons & {"quotaExceeded", "dailyLimitExceeded"}:
        return "YouTube's daily quota is used up. It resets at midnight Pacific time."
    if "uploadLimitExceeded" in reasons:
        return "YouTube's daily upload limit is reached. Try again tomorrow."
    return f"YouTube answered {error.status_code}: {error.reason}"


def video_body(metadata: YouTubeMetadata, publish_at: str) -> dict:
    """What videos.insert sends. Made for kids, always: required by law (COPPA)."""
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": True,
              "containsSyntheticMedia": False,  # for realistic fakes only, not cartoons
              "embeddable": True, "license": "youtube"}
    if publish_at:
        status["publishAt"] = publish_at  # YouTube makes it public by itself at this time
    snippet = {"title": clean(metadata.title)[:100],
               "description": fit_bytes(clean(metadata.description), 5000),
               "tags": fit_tags([clean(tag) for tag in metadata.tags]),
               "categoryId": metadata.category_id,
               "defaultLanguage": metadata.default_language,
               "defaultAudioLanguage": metadata.default_language}
    return {"snippet": snippet, "status": status}


def clean(text: str) -> str:
    return text.replace("<", "").replace(">", "").strip()  # YouTube rejects angle brackets


def fit_bytes(text: str, limit: int) -> str:
    return text.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def fit_tags(tags: list[str], limit: int = 500) -> list[str]:
    """Keep tags while they fit YouTube's 500 characters (a tag with spaces counts its quotes)."""
    kept, used = [], 0
    for tag in filter(None, tags):
        size = len(tag) + (2 if " " in tag else 0) + (1 if kept else 0)  # +1: the comma
        if used + size > limit:
            break
        kept.append(tag)
        used += size
    return kept


def next_slot(times: list[str], taken: set[datetime], now: datetime) -> datetime | None:
    """The first publishing time at least LEAD from now that no other video has. None: no times.

    Times are this PC's local clock; each day gets that day's offset, so summer time is right.
    """
    if not times:
        return None
    clock = sorted(time.fromisoformat(t) for t in times)
    for days in itertools.count():
        for at in clock:
            slot = datetime.combine(now.date() + timedelta(days=days), at).astimezone()
            if slot >= now + LEAD and slot not in taken:
                return slot


def srt(captions: list[dict]) -> str:
    """Caption lines ({text, start, end} in seconds) as an .srt file."""
    def stamp(seconds: float) -> str:
        ms = round(seconds * 1000)
        return f"{ms // 3_600_000:02}:{ms // 60_000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    return "\n".join(f"{n}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
                     for n, c in enumerate(captions, start=1))
