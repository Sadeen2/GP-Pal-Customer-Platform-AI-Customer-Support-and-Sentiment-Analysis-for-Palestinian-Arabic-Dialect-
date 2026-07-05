import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except Exception:  # Keeps the backend running even if openai is not installed.
    OpenAI = None


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1").strip()
OPENAI_TRANSCRIBE_LANGUAGE = os.getenv("OPENAI_TRANSCRIBE_LANGUAGE", "ar").strip()


AUDIO_EXTENSIONS = {
    "audio/aac": ".aac",
    "audio/amr": ".amr",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".mp4",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
}


def _get_whatsapp_credentials() -> dict:
    """Read WhatsApp credentials dynamically from environment variables."""
    return {
        "token": os.getenv("WHATSAPP_ACCESS_TOKEN"),
        "graph_version": os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0"),
    }


def _extension_from_mime_type(mime_type: Optional[str]) -> str:
    if not mime_type:
        return ".ogg"

    # WhatsApp often sends values like: audio/ogg; codecs=opus
    clean_mime = mime_type.split(";")[0].strip().lower()
    return AUDIO_EXTENSIONS.get(clean_mime, ".ogg")


async def download_whatsapp_media(media_id: str) -> dict:
    """
    Download a WhatsApp media file using its media id.

    Meta sends only the media id inside the webhook. The backend must first ask
    Graph API for a temporary media URL, then download the actual file using the
    same access token.
    """
    creds = _get_whatsapp_credentials()
    token = creds["token"]
    graph_version = creds["graph_version"]

    if not token:
        return {
            "ok": False,
            "error": "WHATSAPP_ACCESS_TOKEN is missing",
        }

    if not media_id:
        return {
            "ok": False,
            "error": "media_id is missing",
        }

    headers = {"Authorization": f"Bearer {token}"}
    media_info_url = f"https://graph.facebook.com/{graph_version}/{media_id}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            info_response = await client.get(media_info_url, headers=headers)

            if info_response.status_code not in [200, 201]:
                return {
                    "ok": False,
                    "error": "failed_to_get_media_url",
                    "status_code": info_response.status_code,
                    "response": info_response.text,
                }

            info = info_response.json()
            media_url = info.get("url")
            mime_type = info.get("mime_type") or info.get("mime")

            if not media_url:
                return {
                    "ok": False,
                    "error": "media_url_missing_from_graph_response",
                    "response": info,
                }

            file_response = await client.get(media_url, headers=headers)

            if file_response.status_code not in [200, 201]:
                return {
                    "ok": False,
                    "error": "failed_to_download_media_file",
                    "status_code": file_response.status_code,
                    "response": file_response.text,
                }

        suffix = _extension_from_mime_type(mime_type)

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_response.content)
            file_path = tmp.name

        return {
            "ok": True,
            "file_path": file_path,
            "mime_type": mime_type,
            "media_info": info,
            "size_bytes": len(file_response.content),
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def transcribe_audio_file(file_path: str) -> dict:
    """Convert an audio file to Arabic text using OpenAI speech-to-text."""
    if OpenAI is None:
        return {
            "ok": False,
            "error": "openai package is not installed",
        }

    if not OPENAI_API_KEY:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY is missing",
        }

    if not file_path or not Path(file_path).exists():
        return {
            "ok": False,
            "error": "audio file does not exist",
        }

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        with open(file_path, "rb") as audio_file:
            kwargs = {
                "model": OPENAI_TRANSCRIBE_MODEL,
                "file": audio_file,
            }

            # Arabic is the expected language for this project. It can be changed
            # from .env if needed: OPENAI_TRANSCRIBE_LANGUAGE=en
            if OPENAI_TRANSCRIBE_LANGUAGE:
                kwargs["language"] = OPENAI_TRANSCRIBE_LANGUAGE

            transcription = client.audio.transcriptions.create(**kwargs)

        text = getattr(transcription, "text", None)

        if text is None and isinstance(transcription, dict):
            text = transcription.get("text")

        text = (text or "").strip()

        if not text:
            return {
                "ok": False,
                "error": "empty_transcription",
            }

        return {
            "ok": True,
            "text": text,
            "model": OPENAI_TRANSCRIBE_MODEL,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


async def transcribe_whatsapp_audio(media_id: str) -> dict:
    """
    Full pipeline: WhatsApp media id -> downloaded audio file -> transcript text.
    The temporary audio file is deleted after transcription.
    """
    downloaded = await download_whatsapp_media(media_id)

    if not downloaded.get("ok"):
        return downloaded

    file_path = downloaded.get("file_path")

    try:
        transcription = transcribe_audio_file(file_path)
        transcription["media_id"] = media_id
        transcription["mime_type"] = downloaded.get("mime_type")
        transcription["size_bytes"] = downloaded.get("size_bytes")
        return transcription
    finally:
        try:
            if file_path and Path(file_path).exists():
                Path(file_path).unlink()
        except Exception:
            pass
