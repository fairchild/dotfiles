#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["youtube-transcript-api", "yt-dlp"]
# ///
"""
Fetch YouTube video transcript and metadata.

Usage:
    uv run fetch_youtube.py URL [--transcript-only] [--metadata-only] [--with-segments]

Output:
    JSON to stdout with structure:
    {
        "video_id": "...",
        "metadata": {...},
        "transcript": {...},
        "errors": []
    }
"""

import argparse
import json
import re
import sys
from typing import TypedDict

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


class Metadata(TypedDict, total=False):
    title: str
    channel: str
    description: str
    duration_seconds: int
    duration_formatted: str
    view_count: int
    upload_date: str
    tags: list[str]


class TranscriptSegment(TypedDict):
    start: float
    duration: float
    text: str


class Transcript(TypedDict, total=False):
    text: str
    segments: list[TranscriptSegment]
    language: str


class VideoContent(TypedDict, total=False):
    video_id: str
    metadata: Metadata
    transcript: Transcript
    errors: list[str]


def extract_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",  # bare video ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_metadata(video_id: str) -> tuple[Metadata | None, str | None]:
    """Fetch video metadata via yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            duration = info.get("duration", 0) or 0
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)

            if hours:
                duration_fmt = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_fmt = f"{minutes}:{seconds:02d}"

            return {
                "title": info.get("title", ""),
                "channel": info.get("uploader", ""),
                "description": info.get("description", ""),
                "duration_seconds": duration,
                "duration_formatted": duration_fmt,
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", ""),
                "tags": info.get("tags") or [],
            }, None
    except DownloadError as e:
        return None, f"Video unavailable or download blocked: {e}"
    except ExtractorError as e:
        return None, f"Failed to extract video info: {e}"


def fetch_transcript(
    video_id: str, with_segments: bool = False
) -> tuple[Transcript | None, str | None]:
    """Fetch video transcript via youtube-transcript-api."""
    try:
        api = YouTubeTranscriptApi()
        result = api.fetch(video_id)

        snippets = list(result.snippets)
        full_text = " ".join(s.text for s in snippets)

        transcript: Transcript = {
            "text": full_text,
            "language": result.language_code,
        }

        if with_segments:
            transcript["segments"] = [
                {"start": s.start, "duration": s.duration, "text": s.text}
                for s in snippets
            ]

        return transcript, None

    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video"
    except NoTranscriptFound:
        return None, "No transcript available for this video"
    except VideoUnavailable:
        return None, "Video is unavailable (private, deleted, or restricted)"
    except Exception as e:
        return None, f"Transcript extraction failed ({type(e).__name__}): {e}"


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video content")
    parser.add_argument("url", help="YouTube video URL or video ID")
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Only fetch transcript, skip metadata",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only fetch metadata, skip transcript",
    )
    parser.add_argument(
        "--with-segments",
        action="store_true",
        help="Include timestamped segments (increases output size)",
    )
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(json.dumps({"errors": ["Invalid YouTube URL or video ID"]}))
        sys.exit(1)

    result: VideoContent = {"video_id": video_id, "errors": []}

    if not args.transcript_only:
        metadata, error = fetch_metadata(video_id)
        if metadata:
            result["metadata"] = metadata
        if error:
            result["errors"].append(error)

    if not args.metadata_only:
        transcript, error = fetch_transcript(video_id, with_segments=args.with_segments)
        if transcript:
            result["transcript"] = transcript
        if error:
            result["errors"].append(error)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
