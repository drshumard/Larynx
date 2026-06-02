"""
Text-to-Speech Chunker Backend
FastAPI server for processing long texts into speech using ElevenLabs API
"""

import os
import re
import json
import random
import asyncio
import httpx
import subprocess
import tempfile
from io import BytesIO
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (use explicit path for PM2 compatibility)
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from elevenlabs import ElevenLabs
from elevenlabs.types import PronunciationDictionaryVersionLocator

# Google Drive imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Get ffmpeg path from imageio-ffmpeg (aarch64 compatible)
import imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
print(f"Using ffmpeg from: {FFMPEG_PATH}")

# Environment variables
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "tts_chunker")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "LNHBM9NjjOl44Efsdmtl")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "http://localhost:8001")

# Use paths relative to this script's location for defaults
SCRIPT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = os.environ.get("STORAGE_DIR", str(SCRIPT_DIR / "storage"))
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", str(SCRIPT_DIR / "google-credentials.json"))

# Debug: Print API key status
print(f"ElevenLabs API Key loaded: {'Yes' if ELEVENLABS_API_KEY else 'No'}")
print(f"App Domain: {APP_DOMAIN}")
print(f"Webhook URL: {WEBHOOK_URL or 'Not configured'}")
print(f"Google credentials path: {GOOGLE_CREDENTIALS_PATH}")
print(f"Google credentials exists: {os.path.exists(GOOGLE_CREDENTIALS_PATH) if GOOGLE_CREDENTIALS_PATH else 'Not configured'}")

# Constants
DEFAULT_CHUNK_SIZE = 4500  # Default chunk size for chunking mode
MIN_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 20000
MAX_RETRIES = 3  # Number of retries for failed API calls
RETRY_DELAYS = [5, 15, 30]  # Seconds to wait between retries (exponential backoff)

# Hard per-attempt timeout for ElevenLabs TTS calls (seconds). The SDK uses
# httpx under the hood; without an explicit timeout a streaming response can
# hang the worker thread indefinitely. This bounds each attempt so the retry
# wrapper can surface failures instead of the job silently stalling forever.
ELEVENLABS_REQUEST_TIMEOUT_SECONDS = 240

# ElevenLabs model identifiers
MODEL_MULTILINGUAL_V2 = "eleven_multilingual_v2"

# multilingual_v2 fallback hard cap (used only if chunk_size isn't set; the UI
# `chunk_size` setting is the source of truth at runtime).
V2_HARD_CAP_CHARS = 5000
V2_MAX_PREVIOUS_REQUEST_IDS = 3  # ElevenLabs stitching window

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

# MongoDB client
client: AsyncIOMotorClient = None
db = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    print(f"Connected to MongoDB: {DB_NAME}")
    yield
    client.close()


app = FastAPI(title="TTS Chunker API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models
class JobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=100)  # At least 100 characters
    # Flat webhook passthrough fields (sent back in webhook on completion)
    external_job_id: Optional[str] = Field(None, description="Your external job ID - passed through to webhook")
    files_url: Optional[str] = Field(None, description="Files URL - passed through to webhook")
    callback_data: Optional[str] = Field(None, description="Any extra data - passed through to webhook")
    folder_id: Optional[str] = Field(None, description="Google Drive folder ID to upload audio to")


class JobResponse(BaseModel):
    id: str
    name: str
    status: str
    stage: Optional[str] = None
    progress: int
    chunk_count: int
    processed_chunks: int
    text_length: int
    error: Optional[str] = None
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: str
    updated_at: str


class PronunciationDictionary(BaseModel):
    pronunciation_dictionary_id: str = Field(default="", description="Pronunciation dictionary ID")
    version_id: str = Field(default="", description="Dictionary version ID (optional, uses latest if empty)")


class VoiceSettings(BaseModel):
    stability: float = Field(0.5, ge=0, le=1, description="Controls consistency (0-1)")
    similarity_boost: float = Field(1, ge=0, le=1, description="Voice similarity (0-1)")
    speed: float = Field(1.2, ge=0.5, le=2.0, description="Speech speed (0.5-2.0)")
    style: float = Field(0, ge=0, le=1, description="Expressive style (0-1)")
    use_speaker_boost: bool = Field(False, description="Extra speaker similarity")


class StudioSettings(BaseModel):
    quality_preset: str = Field(default="standard", description="Output quality: standard/high/ultra/ultra_lossless")
    volume_normalization: bool = Field(default=False, description="Audiobook volume normalization")
    apply_text_normalization: str = Field(default="auto", description="Text normalization: auto/on/off/apply_english")


class TTSSettings(BaseModel):
    mode: str = Field(default="chunking", description="TTS mode: chunking or studio")
    voice_id: str = Field(default="LNHBM9NjjOl44Efsdmtl", description="ElevenLabs voice ID")
    model_id: str = Field(default="eleven_v3", description="ElevenLabs model ID")
    output_format: str = Field(default="mp3_44100_128", description="Audio output format (chunking mode)")
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE, description="Chunk size in characters for chunking mode (500-20000)")
    pronunciation_dictionary: Optional[PronunciationDictionary] = Field(default=None, description="Pronunciation dictionary locator")
    voice_settings: VoiceSettings = Field(default_factory=VoiceSettings)
    studio_settings: StudioSettings = Field(default_factory=StudioSettings)


class TTSSettingsUpdate(BaseModel):
    mode: Optional[str] = None
    voice_id: Optional[str] = None
    model_id: Optional[str] = None
    output_format: Optional[str] = None
    chunk_size: Optional[int] = None
    pronunciation_dictionary: Optional[PronunciationDictionary] = None
    voice_settings: Optional[VoiceSettings] = None
    studio_settings: Optional[StudioSettings] = None


# Default TTS settings
DEFAULT_TTS_SETTINGS = {
    "mode": "chunking",
    "voice_id": ELEVENLABS_VOICE_ID,
    "model_id": ELEVENLABS_MODEL,
    "output_format": "mp3_44100_128",
    "chunk_size": DEFAULT_CHUNK_SIZE,
    "pronunciation_dictionary": None,
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 1,
        "speed": 1.2,
        "style": 0,
        "use_speaker_boost": False
    },
    "studio_settings": {
        "quality_preset": "standard",
        "volume_normalization": False,
        "apply_text_normalization": "auto"
    }
}


def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON response."""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [serialize_doc(v) if isinstance(v, dict) else str(v) if isinstance(v, ObjectId) else v.isoformat() if isinstance(v, datetime) else v for v in value]
        else:
            result[key] = value
    return result


async def get_tts_settings():
    """Get current TTS settings from database, or return defaults."""
    settings_doc = await db.settings.find_one({"_id": "tts_settings"})
    if settings_doc:
        # Remove MongoDB _id from result
        del settings_doc["_id"]
        return settings_doc
    return DEFAULT_TTS_SETTINGS.copy()


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """
    Split text at sentence boundaries while keeping chunks under max_chars.
    Sentence boundaries: . ! ? followed by space or newline
    """
    # Split on sentence boundaries but keep the delimiter
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If adding this sentence exceeds max, save current chunk and start new
        if len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If a single sentence exceeds max_chars, we need to split it
            if len(sentence) > max_chars:
                # Split at word boundaries
                words = sentence.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 > max_chars:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = word
                    else:
                        current_chunk = f"{current_chunk} {word}".strip()
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                current_chunk = f"{current_chunk} {sentence}"
            else:
                current_chunk = sentence
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def _split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into sentences while preserving original punctuation
    and any trailing closing quotes/brackets. Splits at . ! ? followed by
    whitespace; does NOT split inside abbreviations perfectly, but is good
    enough to never break mid-sentence at structural boundaries.

    Uses re.finditer on a fixed-width terminator pattern to avoid Python's
    variable-width lookbehind limitation.
    """
    text = text.strip()
    if not text:
        return []
    # Match: any sentence terminator, optionally followed by closing
    # quote/bracket(s), then a whitespace gap to the next sentence.
    terminator_re = re.compile(r'[.!?][\"\'\)\]]*(?=\s+)')
    sentences: list[str] = []
    last = 0
    for m in terminator_re.finditer(text):
        end = m.end()
        # Peek at next non-space char; only treat as boundary when followed by
        # a likely sentence-starter (capital letter, digit, or opening quote).
        rest = text[end:]
        stripped = rest.lstrip()
        if not stripped:
            continue
        nxt = stripped[0]
        if not (nxt.isupper() or nxt.isdigit() or nxt in '"\'([{'):
            continue
        sentences.append(text[last:end].strip())
        last = end + (len(rest) - len(stripped))
    tail = text[last:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def split_text_into_chunks_v2(
    text: str,
    hard_cap: int = V2_HARD_CAP_CHARS,
) -> list[str]:
    """
    Chunker for ElevenLabs `eleven_multilingual_v2` request stitching.

    Rules:
      - Hard cap: `hard_cap` chars per chunk (driven by the UI `chunk_size`
        setting — falls back to V2_HARD_CAP_CHARS only when not provided).
      - Prefer PARAGRAPH boundaries (\n\n). When a paragraph alone exceeds the
        hard cap, fall back to sentence-level packing inside that paragraph.
      - NEVER split mid-sentence (only at sentence terminators . ! ?). If a
        single sentence exceeds `hard_cap`, it is emitted as-is rather than
        broken mid-sentence — prosody integrity is preserved over API safety.
      - Preserves original punctuation/whitespace within sentences.

    Strategy: greedy pack. Add the next unit (paragraph, else sentence) while
    it fits under `hard_cap`. Close the chunk as soon as the next unit would
    overflow. No soft target — pack as full as possible.
    """
    if not text or not text.strip():
        return []

    # Treat 2+ consecutive newlines as paragraph boundaries.
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n+', text.strip()) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    # Expand any paragraph that exceeds hard_cap into its constituent sentences.
    units: list[tuple[str, str]] = []  # (kind, text), kind in {"para","sent"}
    for para in paragraphs:
        if len(para) <= hard_cap:
            units.append(("para", para))
        else:
            sentences = _split_into_sentences(para)
            if not sentences:
                # Degenerate: a single block longer than hard_cap with no
                # terminators. Emit as-is — never split mid-sentence.
                units.append(("sent", para))
            else:
                for s in sentences:
                    units.append(("sent", s))

    chunks: list[str] = []
    cur_parts: list[tuple[str, str]] = []
    cur_len = 0

    def _flush():
        nonlocal cur_parts, cur_len
        if not cur_parts:
            return
        out = ""
        for idx, (kind, t) in enumerate(cur_parts):
            if idx == 0:
                out = t
            else:
                prev_kind = cur_parts[idx - 1][0]
                sep = "\n\n" if (kind == "para" and prev_kind == "para") else " "
                out = f"{out}{sep}{t}"
        chunks.append(out.strip())
        cur_parts = []
        cur_len = 0

    for kind, t in units:
        t_len = len(t)
        sep_cost = 0
        if cur_parts:
            prev_kind = cur_parts[-1][0]
            sep_cost = 2 if (kind == "para" and prev_kind == "para") else 1

        projected = cur_len + sep_cost + t_len

        if cur_parts and projected > hard_cap:
            # Would overflow the API limit — close current chunk first.
            _flush()
            cur_parts.append((kind, t))
            cur_len = t_len
        else:
            cur_parts.append((kind, t))
            cur_len = projected if (cur_parts and len(cur_parts) > 1) else t_len

    _flush()
    return chunks


async def tts_chunk_to_audio(client: ElevenLabs, text: str, settings: dict) -> bytes:
    """
    Convert text chunk to audio using ElevenLabs TTS API.
    Returns MP3 bytes.
    """
    voice_settings = settings.get("voice_settings", {})
    
    # Build pronunciation dictionary locators if configured
    pronunciation_dict = settings.get("pronunciation_dictionary")
    pronunciation_dictionary_locators = None
    if pronunciation_dict and pronunciation_dict.get("pronunciation_dictionary_id"):
        locator = PronunciationDictionaryVersionLocator(
            pronunciation_dictionary_id=pronunciation_dict["pronunciation_dictionary_id"],
            version_id=pronunciation_dict.get("version_id") or None
        )
        pronunciation_dictionary_locators = [locator]
        print(f"Using pronunciation dictionary: {pronunciation_dict['pronunciation_dictionary_id']}")
    
    # Use the text_to_speech.convert method from the SDK
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=settings.get("voice_id", ELEVENLABS_VOICE_ID),
        model_id=settings.get("model_id", ELEVENLABS_MODEL),
        output_format=settings.get("output_format", "mp3_44100_128"),
        voice_settings={
            "stability": voice_settings.get("stability", 0.5),
            "similarity_boost": voice_settings.get("similarity_boost", 1),
            "speed": voice_settings.get("speed", 1.2),
            "style": voice_settings.get("style", 0),
            "use_speaker_boost": voice_settings.get("use_speaker_boost", False)
        },
        pronunciation_dictionary_locators=pronunciation_dictionary_locators
    )
    
    # Collect all audio bytes from generator
    audio_data = b""
    for chunk in audio_generator:
        audio_data += chunk
    
    return audio_data


def merge_audio_chunks(audio_chunks: list[bytes]) -> tuple[bytes, float]:
    """
    Merge multiple MP3 audio chunks into a single MP3 file using ffmpeg directly.
    Returns (merged_bytes, duration_seconds)
    """
    if not audio_chunks:
        raise ValueError("No audio chunks to merge")
    
    # If only one chunk, return it directly
    if len(audio_chunks) == 1:
        # Get duration using ffmpeg
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(audio_chunks[0])
            tmp_path = tmp.name
        
        try:
            # Get duration using ffmpeg
            result = subprocess.run(
                [FFMPEG_PATH, '-i', tmp_path, '-f', 'null', '-'],
                capture_output=True,
                text=True
            )
            # Parse duration from stderr (ffmpeg outputs info there)
            duration = 0.0
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    time_str = line.split('Duration:')[1].split(',')[0].strip()
                    parts = time_str.split(':')
                    if len(parts) == 3:
                        h, m, s = parts
                        duration = float(h) * 3600 + float(m) * 60 + float(s)
                    break
            return audio_chunks[0], duration
        finally:
            os.unlink(tmp_path)
    
    # Multiple chunks - create temp files and merge
    temp_files = []
    try:
        # Write all chunks to temp files
        for i, chunk in enumerate(audio_chunks):
            tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tmp.write(chunk)
            tmp.close()
            temp_files.append(tmp.name)
        
        # Create concat file for ffmpeg
        concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        for f in temp_files:
            concat_file.write(f"file '{f}'\n")
        concat_file.close()
        
        # Output file
        output_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        output_file.close()
        
        # Run ffmpeg concat
        result = subprocess.run(
            [
                FFMPEG_PATH,
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c', 'copy',
                '-y',
                output_file.name
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg merge failed: {result.stderr}")
        
        # Read merged file
        with open(output_file.name, 'rb') as f:
            merged_data = f.read()
        
        # Get duration from the merged file
        result = subprocess.run(
            [FFMPEG_PATH, '-i', output_file.name, '-f', 'null', '-'],
            capture_output=True,
            text=True
        )
        duration = 0.0
        for line in result.stderr.split('\n'):
            if 'Duration:' in line:
                time_str = line.split('Duration:')[1].split(',')[0].strip()
                parts = time_str.split(':')
                if len(parts) == 3:
                    h, m, s = parts
                    duration = float(h) * 3600 + float(m) * 60 + float(s)
                break
        
        # Clean up
        os.unlink(concat_file.name)
        os.unlink(output_file.name)
        
        return merged_data, duration
        
    finally:
        # Clean up temp files
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass


async def send_webhook(job_id: str, name: str, audio_url: str, status: str, text_length: int, chunk_count: int, external_job_id: str = None, files_url: str = None, callback_data: str = None, google_drive_url: str = None, google_drive_file_id: str = None):
    """Send webhook notification on job completion."""
    if not WEBHOOK_URL:
        print("No webhook URL configured, skipping...")
        return False
    
    payload = {
        "jobId": job_id,
        "name": name,
        "audioUrl": audio_url,
        "status": status,
        "textLength": text_length,
        "chunkCount": chunk_count,
        "completedAt": datetime.utcnow().isoformat()
    }
    
    # Add passthrough fields if provided
    if external_job_id:
        payload["externalJobId"] = external_job_id
    if files_url:
        payload["filesUrl"] = files_url
    if callback_data:
        payload["callbackData"] = callback_data
    if google_drive_url:
        payload["googleDriveUrl"] = google_drive_url
    if google_drive_file_id:
        payload["googleDriveFileId"] = google_drive_file_id
    
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(WEBHOOK_URL, json=payload, timeout=10.0)
            print(f"Webhook sent: {response.status_code}")
            return response.status_code in (200, 201, 202, 204)
    except Exception as e:
        print(f"Webhook error: {e}")
        return False


def upload_to_google_drive(file_path: str, folder_id: str, file_name: str) -> dict:
    """
    Upload a file to Google Drive folder (supports Shared Drives).
    Returns dict with file_id and web_view_link.
    """
    try:
        if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
            print(f"Google credentials file not found: {GOOGLE_CREDENTIALS_PATH}")
            return None
        
        # Authenticate with service account - use full drive scope for Shared Drive access
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # Build the Drive service
        service = build('drive', 'v3', credentials=credentials)
        
        # File metadata
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # Upload the file with supportsAllDrives for Shared Drive compatibility
        media = MediaFileUpload(file_path, mimetype='audio/mpeg', resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink',
            supportsAllDrives=True  # Required for Shared Drives
        ).execute()
        
        print(f"Uploaded to Google Drive: {file.get('id')}")
        
        return {
            'file_id': file.get('id'),
            'web_view_link': file.get('webViewLink'),
            'web_content_link': file.get('webContentLink')
        }
        
    except Exception as e:
        print(f"Google Drive upload error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def process_studio_job(job_id: str):
    """Background task to process TTS job using ElevenLabs Studio API."""
    try:
        # Get job from database
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            print(f"Job {job_id} not found")
            return
        
        # Get TTS settings from job
        tts_config = job.get("tts_config", DEFAULT_TTS_SETTINGS)
        voice_settings = tts_config.get("voice_settings", {})
        studio_settings = tts_config.get("studio_settings", {})
        
        # Update status
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "processing", "stage": "Creating Studio project...", "progress": 10, "updated_at": datetime.utcnow()}}
        )
        
        # Prepare the content JSON for Studio API
        # Split text into paragraphs for better structure
        text = job.get("original_text", "")
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        
        # Build blocks with TTS nodes
        voice_id = tts_config.get("voice_id", ELEVENLABS_VOICE_ID)
        blocks = []
        for para in paragraphs:
            if para:
                blocks.append({
                    "sub_type": "p",
                    "nodes": [{
                        "voice_id": voice_id,
                        "text": para,
                        "type": "tts_node"
                    }]
                })
        
        # Create content JSON with single chapter
        content_json = [{
            "name": job.get("name", "Chapter 1"),
            "blocks": blocks
        }]
        
        # Build voice settings override
        voice_settings_override = [{
            "voice_id": voice_id,
            "stability": voice_settings.get("stability", 0.5),
            "similarity_boost": voice_settings.get("similarity_boost", 1),
            "style": voice_settings.get("style", 0),
            "speed": voice_settings.get("speed", 1.2),
            "use_speaker_boost": voice_settings.get("use_speaker_boost", False)
        }]
        
        # Prepare form data for Studio API
        form_data = {
            "name": job.get("name", "TTS Project"),
            "default_paragraph_voice_id": voice_id,
            "default_model_id": tts_config.get("model_id", ELEVENLABS_MODEL),
            "quality_preset": studio_settings.get("quality_preset", "standard"),
            "volume_normalization": str(studio_settings.get("volume_normalization", False)).lower(),
            "apply_text_normalization": studio_settings.get("apply_text_normalization", "auto"),
            "auto_convert": "true",
            "from_content_json": str(content_json).replace("'", '"')
        }
        
        # Add voice settings as JSON strings
        for vs in voice_settings_override:
            form_data["voice_settings"] = str(vs).replace("'", '"').replace("True", "true").replace("False", "false")
        
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        print(f"Creating Studio project for job {job_id}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Create Studio project with auto_convert
            response = await client.post(
                "https://api.elevenlabs.io/v1/studio/projects",
                data=form_data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_msg = f"Studio API error: {response.status_code} - {response.text}"
                print(error_msg)
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
                )
                return
            
            project_data = response.json()
            project_id = project_data.get("project", {}).get("project_id")
            
            if not project_id:
                error_msg = "Failed to get project_id from Studio API response"
                print(error_msg)
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
                )
                return
            
            print(f"Studio project created: {project_id}")
            
            # Store project_id in job
            await db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "studio_project_id": project_id,
                    "stage": "Converting audio...",
                    "progress": 30,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Poll for project conversion status
            max_attempts = 120  # 10 minutes max
            attempt = 0
            project_snapshot_id = None
            
            while attempt < max_attempts:
                await asyncio.sleep(5)  # Wait 5 seconds between polls
                attempt += 1
                
                # Get project status
                status_response = await client.get(
                    f"https://api.elevenlabs.io/v1/studio/projects/{project_id}",
                    headers=headers
                )
                
                if status_response.status_code != 200:
                    continue
                
                project_status = status_response.json()
                state = project_status.get("state")
                
                # Update progress
                progress = min(30 + (attempt * 50 // max_attempts), 80)
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {
                        "stage": f"Converting audio... ({state})",
                        "progress": progress,
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                if state == "ready":
                    # Get the latest snapshot
                    snapshots_response = await client.get(
                        f"https://api.elevenlabs.io/v1/studio/projects/{project_id}/snapshots",
                        headers=headers
                    )
                    
                    if snapshots_response.status_code == 200:
                        snapshots_data = snapshots_response.json()
                        snapshots = snapshots_data.get("snapshots", [])
                        if snapshots:
                            project_snapshot_id = snapshots[0].get("project_snapshot_id")
                            break
                
                elif state == "failed":
                    error_msg = f"Studio conversion failed: {project_status.get('error', 'Unknown error')}"
                    print(error_msg)
                    await db.jobs.update_one(
                        {"_id": ObjectId(job_id)},
                        {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
                    )
                    return
            
            if not project_snapshot_id:
                error_msg = "Timeout waiting for Studio conversion"
                print(error_msg)
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
                )
                return
            
            print(f"Studio conversion complete, snapshot: {project_snapshot_id}")
            
            # Update status
            await db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "studio_snapshot_id": project_snapshot_id,
                    "stage": "Downloading audio...",
                    "progress": 85,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Download the audio
            audio_response = await client.get(
                f"https://api.elevenlabs.io/v1/studio/projects/{project_id}/snapshots/{project_snapshot_id}/stream",
                headers=headers
            )
            
            if audio_response.status_code != 200:
                error_msg = f"Failed to download audio: {audio_response.status_code}"
                print(error_msg)
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
                )
                return
            
            # Save audio file
            audio_path = os.path.join(STORAGE_DIR, f"{job_id}.mp3")
            with open(audio_path, "wb") as f:
                f.write(audio_response.content)
            
            # Get audio duration using ffprobe
            duration = None
            try:
                result = subprocess.run(
                    [FFMPEG_PATH.replace('ffmpeg', 'ffprobe'), '-v', 'quiet', '-show_entries', 
                     'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    duration = float(result.stdout.strip())
            except:
                pass
            
            # Update job as completed
            audio_url = f"/api/jobs/{job_id}/download"
            full_audio_url = f"{APP_DOMAIN}{audio_url}"
            
            # Upload to Google Drive if folder_id is provided
            google_drive_url = None
            google_drive_file_id = None
            folder_id = job.get("folder_id")
            if folder_id and audio_path:
                print(f"Uploading to Google Drive folder: {folder_id}")
                file_name = f"{job.get('name', 'audio')}_{job_id}.mp3"
                drive_result = upload_to_google_drive(audio_path, folder_id, file_name)
                if drive_result:
                    google_drive_url = drive_result.get('web_view_link')
                    google_drive_file_id = drive_result.get('file_id')
                    print(f"Google Drive upload successful: {google_drive_file_id}")
            
            await db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "status": "completed",
                    "stage": "Complete",
                    "progress": 100,
                    "processed_chunks": 1,
                    "audio_path": audio_path,
                    "audio_url": audio_url,
                    "duration_seconds": duration,
                    "google_drive_url": google_drive_url,
                    "google_drive_file_id": google_drive_file_id,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            print(f"Studio job {job_id} completed. Duration: {duration}s")
            
            # Send webhook notification
            if WEBHOOK_URL:
                await send_webhook(
                    job_id=job_id,
                    name=job.get("name"),
                    audio_url=full_audio_url,
                    status="completed",
                    text_length=len(text),
                    chunk_count=1,
                    external_job_id=job.get("external_job_id"),
                    files_url=job.get("files_url"),
                    callback_data=job.get("callback_data"),
                    google_drive_url=google_drive_url,
                    google_drive_file_id=google_drive_file_id
                )
    
    except Exception as e:
        error_msg = f"Studio processing error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "failed", "error": error_msg, "updated_at": datetime.utcnow()}}
        )


async def process_tts_job(job_id: str):
    """Background task to process TTS job."""
    try:
        # Get job from database
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            print(f"Job {job_id} not found")
            return
        
        # Get TTS settings from job (stored at creation time)
        tts_settings = job.get("tts_config", DEFAULT_TTS_SETTINGS)
        
        # Update status to chunking
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "chunking", "stage": "Analyzing text...", "updated_at": datetime.utcnow()}}
        )
        
        # Initialize ElevenLabs client
        eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Get chunks
        chunks = job["chunks"]
        chunk_count = len(chunks)
        audio_chunks = []
        
        # Request-stitching state (only used for multilingual_v2).
        model_id = tts_settings.get("model_id", ELEVENLABS_MODEL)
        stitching_enabled = (model_id == MODEL_MULTILINGUAL_V2)
        job_seed: Optional[int] = job.get("seed") if stitching_enabled else None
        request_ids: list = []
        if stitching_enabled:
            print(f"Job {job_id}: stitching ON (model={model_id}, seed={job_seed})")
        
        # Update status to transcribing
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "transcribing", "stage": f"Converting to speech (0/{chunk_count})...", "updated_at": datetime.utcnow()}}
        )
        
        # Process each chunk with retry logic
        for i, chunk_text in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{chunk_count} for job {job_id}")
            
            # Update chunk status to processing
            await db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    f"chunk_requests.{i}.status": "processing",
                    "updated_at": datetime.utcnow()
                }}
            )
            
            try:
                # Use retry wrapper for resilience. Thread stitching state when active.
                prev_ids = request_ids[-V2_MAX_PREVIOUS_REQUEST_IDS:] if stitching_enabled and request_ids else None
                audio_data, chunk_request_id = await tts_chunk_with_retry(
                    eleven_client, chunk_text, tts_settings, i, job_id,
                    seed=job_seed,
                    previous_request_ids=prev_ids,
                )
                audio_chunks.append(audio_data)
                if stitching_enabled and chunk_request_id:
                    request_ids.append(chunk_request_id)
                
                # Save individual chunk audio file
                chunk_audio_path = os.path.join(STORAGE_DIR, f"{job_id}_chunk_{i}.mp3")
                with open(chunk_audio_path, "wb") as f:
                    f.write(audio_data)
                
                # Update progress and chunk request status
                progress = int(((i + 1) / chunk_count) * 85)  # 85% for TTS, 15% for merge
                chunk_update = {
                    "processed_chunks": i + 1,
                    "progress": progress,
                    "stage": f"Converting to speech ({i + 1}/{chunk_count})...",
                    "updated_at": datetime.utcnow(),
                    f"chunk_requests.{i}.status": "completed",
                    f"chunk_requests.{i}.processed_at": datetime.utcnow().isoformat(),
                    f"chunk_requests.{i}.audio_path": chunk_audio_path,
                    f"chunk_requests.{i}.audio_url": f"/api/jobs/{job_id}/chunks/{i}/audio",
                }
                if stitching_enabled:
                    chunk_update[f"chunk_requests.{i}.request_id"] = chunk_request_id
                    chunk_update[f"chunk_requests.{i}.previous_request_ids"] = prev_ids or []
                    chunk_update[f"chunk_requests.{i}.seed"] = job_seed
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": chunk_update}
                )
            except Exception as e:
                # Mark chunk as failed after all retries exhausted
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            f"chunk_requests.{i}.status": "failed",
                            f"chunk_requests.{i}.error": str(e),
                            f"chunk_requests.{i}.processed_at": datetime.utcnow().isoformat(),
                            "failed_at_chunk": i  # Track where we failed for resume
                        }
                    }
                )
                print(f"Error processing chunk {i + 1} after {MAX_RETRIES} retries: {e}")
                raise
        
        # Merge audio chunks
        print(f"Merging {len(audio_chunks)} audio chunks for job {job_id}")
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "merging", "stage": "Merging audio chunks...", "progress": 90, "updated_at": datetime.utcnow()}}
        )
        
        merged_audio, duration = await asyncio.to_thread(
            merge_audio_chunks, audio_chunks
        )
        
        # Save to file
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"stage": "Saving audio file...", "progress": 95, "updated_at": datetime.utcnow()}}
        )
        
        audio_path = os.path.join(STORAGE_DIR, f"{job_id}.mp3")
        with open(audio_path, "wb") as f:
            f.write(merged_audio)
        
        # Upload to Google Drive if folder_id is provided
        google_drive_url = None
        google_drive_file_id = None
        folder_id = job.get("folder_id")
        if folder_id and audio_path:
            print(f"Uploading to Google Drive folder: {folder_id}")
            file_name = f"{job.get('name', 'audio')}_{job_id}.mp3"
            drive_result = upload_to_google_drive(audio_path, folder_id, file_name)
            if drive_result:
                google_drive_url = drive_result.get('web_view_link')
                google_drive_file_id = drive_result.get('file_id')
                print(f"Google Drive upload successful: {google_drive_file_id}")
        
        # Update job as completed
        audio_url = f"/api/jobs/{job_id}/download"
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "stage": "Complete",
                    "audio_path": audio_path,
                    "audio_url": audio_url,
                    "duration_seconds": duration,
                    "google_drive_url": google_drive_url,
                    "google_drive_file_id": google_drive_file_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"Job {job_id} completed. Duration: {duration:.2f}s")
        
        # Send webhook
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        full_audio_url = f"{APP_DOMAIN}{audio_url}"
        await send_webhook(
            job_id=job_id,
            name=job["name"],
            audio_url=full_audio_url,
            status="completed",
            text_length=job["text_length"],
            chunk_count=chunk_count,
            external_job_id=job.get("external_job_id"),
            files_url=job.get("files_url"),
            callback_data=job.get("callback_data"),
            google_drive_url=google_drive_url,
            google_drive_file_id=google_drive_file_id
        )
        
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.utcnow()
                }
            }
        )


def tts_chunk_to_audio_sync(
    client: ElevenLabs,
    text: str,
    settings: dict,
    seed: Optional[int] = None,
    previous_request_ids: Optional[list] = None,
) -> tuple[bytes, Optional[str]]:
    """
    Synchronous TTS conversion.

    Returns (audio_bytes, request_id).

    When `seed` or `previous_request_ids` are supplied (multilingual_v2
    stitching path), uses `with_raw_response.convert` so the `request-id`
    response header is captured and returned. Otherwise falls back to the
    plain streaming convert and returns request_id=None for behavioral
    parity with the pre-stitching pipeline.
    """
    voice_settings = settings.get("voice_settings", {})
    
    # Build pronunciation dictionary locators if configured
    pronunciation_dict = settings.get("pronunciation_dictionary")
    pronunciation_dictionary_locators = None
    if pronunciation_dict and pronunciation_dict.get("pronunciation_dictionary_id"):
        locator = PronunciationDictionaryVersionLocator(
            pronunciation_dictionary_id=pronunciation_dict["pronunciation_dictionary_id"],
            version_id=pronunciation_dict.get("version_id") or None
        )
        pronunciation_dictionary_locators = [locator]
        print(f"Using pronunciation dictionary: {pronunciation_dict['pronunciation_dictionary_id']}")
    
    voice_id = settings.get("voice_id", ELEVENLABS_VOICE_ID)
    model_id = settings.get("model_id", ELEVENLABS_MODEL)
    output_format = settings.get("output_format", "mp3_44100_128")
    vs_payload = {
        "stability": voice_settings.get("stability", 0.5),
        "similarity_boost": voice_settings.get("similarity_boost", 1),
        "speed": voice_settings.get("speed", 1.2),
        "style": voice_settings.get("style", 0),
        "use_speaker_boost": voice_settings.get("use_speaker_boost", False),
    }

    # Bound every attempt with a hard timeout so a hung HTTP read can't
    # silently stall a job forever. The SDK forwards this into httpx.
    request_options = {"timeout_in_seconds": ELEVENLABS_REQUEST_TIMEOUT_SECONDS}

    use_raw = seed is not None or bool(previous_request_ids)

    if use_raw:
        # Stitching path: capture request-id header from raw response.
        kwargs = dict(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
            voice_settings=vs_payload,
            pronunciation_dictionary_locators=pronunciation_dictionary_locators,
            request_options=request_options,
        )
        if seed is not None:
            kwargs["seed"] = seed
        if previous_request_ids:
            # Cap at the ElevenLabs stitching window.
            kwargs["previous_request_ids"] = list(previous_request_ids)[-V2_MAX_PREVIOUS_REQUEST_IDS:]

        with client.text_to_speech.with_raw_response.convert(**kwargs) as response:
            # SDK 2.x exposes headers on the HttpResponse object directly.
            request_id = None
            try:
                request_id = response.headers.get("request-id")
            except Exception:
                request_id = None
            audio_data = b"".join(chunk for chunk in response.data)

        return audio_data, request_id

    # Legacy path — unchanged behavior for non-stitching models.
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        voice_settings=vs_payload,
        pronunciation_dictionary_locators=pronunciation_dictionary_locators,
        request_options=request_options,
    )
    audio_data = b"".join(chunk for chunk in audio_generator)
    return audio_data, None


async def tts_chunk_with_retry(
    eleven_client: ElevenLabs,
    chunk_text: str,
    tts_settings: dict,
    chunk_index: int,
    job_id: str,
    seed: Optional[int] = None,
    previous_request_ids: Optional[list] = None,
) -> tuple[bytes, Optional[str]]:
    """
    Process a TTS chunk with automatic retry on failure.
    Returns (audio_bytes, request_id) on success; raises after all retries exhausted.

    When `seed` and/or `previous_request_ids` are supplied, the underlying call
    uses ElevenLabs request stitching (multilingual_v2 only) and captures the
    `request-id` response header so the caller can chain it forward.
    """
    last_error = None
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            if attempt > 0:
                delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                print(f"Retry {attempt}/{MAX_RETRIES} for chunk {chunk_index + 1} of job {job_id} after {delay}s delay...")
                await asyncio.sleep(delay)
                
                # Update chunk status to retrying
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {
                        f"chunk_requests.{chunk_index}.status": "retrying",
                        f"chunk_requests.{chunk_index}.retry_count": attempt,
                        "updated_at": datetime.utcnow()
                    }}
                )
            
            audio_data, request_id = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda ct=chunk_text, s=tts_settings, sd=seed, pri=previous_request_ids:
                        tts_chunk_to_audio_sync(eleven_client, ct, s, seed=sd, previous_request_ids=pri)
                ),
                timeout=ELEVENLABS_REQUEST_TIMEOUT_SECONDS,
            )
            return audio_data, request_id
            
        except Exception as e:
            last_error = e
            print(f"Chunk {chunk_index + 1} attempt {attempt + 1} failed: {e}")
            
            if attempt < MAX_RETRIES:
                # Update chunk status with error but continue retrying
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {
                        f"chunk_requests.{chunk_index}.last_error": str(e),
                        f"chunk_requests.{chunk_index}.retry_count": attempt + 1,
                        "updated_at": datetime.utcnow()
                    }}
                )
    
    # All retries exhausted
    raise last_error


# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "tts-chunker"}


@app.get("/api/settings")
async def get_settings():
    """Get current TTS settings."""
    settings = await get_tts_settings()
    return settings


@app.put("/api/settings")
async def update_settings(settings: TTSSettings):
    """Update TTS settings. Settings persist until changed again."""
    # Handle pronunciation dictionary
    pronunciation_dict = None
    if settings.pronunciation_dictionary:
        pronunciation_dict = {
            "pronunciation_dictionary_id": settings.pronunciation_dictionary.pronunciation_dictionary_id,
            "version_id": settings.pronunciation_dictionary.version_id
        }
    
    settings_dict = {
        "mode": settings.mode,
        "voice_id": settings.voice_id,
        "model_id": settings.model_id,
        "output_format": settings.output_format,
        "chunk_size": settings.chunk_size,
        "pronunciation_dictionary": pronunciation_dict,
        "voice_settings": {
            "stability": settings.voice_settings.stability,
            "similarity_boost": settings.voice_settings.similarity_boost,
            "speed": settings.voice_settings.speed,
            "style": settings.voice_settings.style,
            "use_speaker_boost": settings.voice_settings.use_speaker_boost
        },
        "studio_settings": {
            "quality_preset": settings.studio_settings.quality_preset,
            "volume_normalization": settings.studio_settings.volume_normalization,
            "apply_text_normalization": settings.studio_settings.apply_text_normalization
        }
    }
    
    # Upsert settings document
    await db.settings.update_one(
        {"_id": "tts_settings"},
        {"$set": settings_dict},
        upsert=True
    )
    
    return {"message": "Settings updated successfully", "settings": settings_dict}


@app.patch("/api/settings")
async def patch_settings(updates: TTSSettingsUpdate):
    """Partially update TTS settings. Only provided fields are updated."""
    current_settings = await get_tts_settings()
    
    # Apply updates
    if updates.mode is not None:
        current_settings["mode"] = updates.mode
    if updates.voice_id is not None:
        current_settings["voice_id"] = updates.voice_id
    if updates.model_id is not None:
        current_settings["model_id"] = updates.model_id
    if updates.output_format is not None:
        current_settings["output_format"] = updates.output_format
    if updates.chunk_size is not None:
        current_settings["chunk_size"] = updates.chunk_size
    if updates.pronunciation_dictionary is not None:
        pd = updates.pronunciation_dictionary
        current_settings["pronunciation_dictionary"] = {
            "pronunciation_dictionary_id": pd.pronunciation_dictionary_id,
            "version_id": pd.version_id
        }
    if updates.voice_settings is not None:
        vs = updates.voice_settings
        current_vs = current_settings.get("voice_settings", {})
        current_vs["stability"] = vs.stability
        current_vs["similarity_boost"] = vs.similarity_boost
        current_vs["speed"] = vs.speed
        current_vs["style"] = vs.style
        current_vs["use_speaker_boost"] = vs.use_speaker_boost
        current_settings["voice_settings"] = current_vs
    if updates.studio_settings is not None:
        ss = updates.studio_settings
        current_ss = current_settings.get("studio_settings", {})
        current_ss["quality_preset"] = ss.quality_preset
        current_ss["volume_normalization"] = ss.volume_normalization
        current_ss["apply_text_normalization"] = ss.apply_text_normalization
        current_settings["studio_settings"] = current_ss
    
    # Upsert settings document
    await db.settings.update_one(
        {"_id": "tts_settings"},
        {"$set": current_settings},
        upsert=True
    )
    
    return {"message": "Settings updated successfully", "settings": current_settings}


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset TTS settings to defaults."""
    await db.settings.delete_one({"_id": "tts_settings"})
    return {"message": "Settings reset to defaults", "settings": DEFAULT_TTS_SETTINGS}


@app.post("/api/jobs", response_model=JobResponse)
async def create_job(job_data: JobCreate, background_tasks: BackgroundTasks):
    """Create a new TTS job."""
    # Get current TTS settings
    tts_settings = await get_tts_settings()
    mode = tts_settings.get("mode", "chunking")
    voice_settings = tts_settings.get("voice_settings", DEFAULT_TTS_SETTINGS["voice_settings"])
    studio_settings = tts_settings.get("studio_settings", DEFAULT_TTS_SETTINGS["studio_settings"])
    
    # For chunking mode, split text into chunks
    # For studio mode, we don't chunk - Studio handles it
    if mode == "chunking":
        model_id = tts_settings.get("model_id", ELEVENLABS_MODEL)
        chunk_size = tts_settings.get("chunk_size", DEFAULT_CHUNK_SIZE)
        if model_id == MODEL_MULTILINGUAL_V2:
            # multilingual_v2: request stitching + sentence-only splits.
            # UI `chunk_size` acts as the hard cap (same source of truth as
            # all other models).
            chunks = split_text_into_chunks_v2(job_data.text, hard_cap=chunk_size)
        else:
            chunks = split_text_into_chunks(job_data.text, max_chars=chunk_size)
        if len(chunks) == 0:
            raise HTTPException(status_code=400, detail="Text is too short to process")
        chunk_count = len(chunks)
    else:
        # Studio mode - single "chunk" containing all text
        chunks = [job_data.text]
        chunk_count = 1
    
    chunk_requests = []
    pronunciation_dict = tts_settings.get("pronunciation_dictionary")
    for i, chunk_text in enumerate(chunks):
        if mode == "chunking":
            chunk_requests.append({
                "chunk_index": i,
                "request": {
                    "endpoint": "POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    "voice_id": tts_settings.get("voice_id", ELEVENLABS_VOICE_ID),
                    "model_id": tts_settings.get("model_id", ELEVENLABS_MODEL),
                    "output_format": tts_settings.get("output_format", "mp3_44100_128"),
                    "voice_settings": voice_settings,
                    "pronunciation_dictionary_locators": [pronunciation_dict] if pronunciation_dict and pronunciation_dict.get("pronunciation_dictionary_id") else None,
                    "text": chunk_text,
                    "text_length": len(chunk_text)
                },
                "status": "pending",
                "processed_at": None
            })
        else:
            # Studio mode request structure
            chunk_requests.append({
                "chunk_index": i,
                "request": {
                    "endpoint": "POST https://api.elevenlabs.io/v1/studio/projects",
                    "voice_id": tts_settings.get("voice_id", ELEVENLABS_VOICE_ID),
                    "model_id": tts_settings.get("model_id", ELEVENLABS_MODEL),
                    "quality_preset": studio_settings.get("quality_preset", "standard"),
                    "voice_settings": voice_settings,
                    "studio_settings": studio_settings,
                    "text_length": len(chunk_text)
                },
                "status": "pending",
                "processed_at": None
            })
    
    # Create job document
    now = datetime.utcnow()
    # Generate a per-job random seed for multilingual_v2 stitching.
    job_seed: Optional[int] = None
    if mode == "chunking" and tts_settings.get("model_id", ELEVENLABS_MODEL) == MODEL_MULTILINGUAL_V2:
        job_seed = random.randint(0, 2**31 - 1)
    job_doc = {
        "name": job_data.name,
        "text_length": len(job_data.text),
        "original_text": job_data.text,  # Store original text for Studio mode
        "chunk_count": chunk_count,
        "processed_chunks": 0,
        "chunks": chunks,
        "chunk_requests": chunk_requests,
        "external_job_id": job_data.external_job_id,
        "files_url": job_data.files_url,
        "callback_data": job_data.callback_data,
        "folder_id": job_data.folder_id,
        "seed": job_seed,  # multilingual_v2 stitching seed (null otherwise)
        "tts_config": {
            "api": "ElevenLabs",
            "mode": mode,
            "voice_id": tts_settings.get("voice_id", ELEVENLABS_VOICE_ID),
            "model_id": tts_settings.get("model_id", ELEVENLABS_MODEL),
            "output_format": tts_settings.get("output_format", "mp3_44100_128"),
            "chunk_size": tts_settings.get("chunk_size", DEFAULT_CHUNK_SIZE) if mode == "chunking" else None,
            "pronunciation_dictionary": tts_settings.get("pronunciation_dictionary"),
            "voice_settings": voice_settings,
            "studio_settings": studio_settings
        },
        "status": "queued",
        "stage": "Waiting in queue...",
        "progress": 0,
        "error": None,
        "audio_path": None,
        "audio_url": None,
        "duration_seconds": None,
        "created_at": now,
        "updated_at": now
    }
    
    # Insert into database
    result = await db.jobs.insert_one(job_doc)
    job_id = str(result.inserted_id)
    
    # Start background processing based on mode
    if mode == "studio":
        background_tasks.add_task(process_studio_job, job_id)
    else:
        background_tasks.add_task(process_tts_job, job_id)
    
    # Return response
    job_doc["_id"] = result.inserted_id
    serialized = serialize_doc(job_doc)
    
    return JobResponse(
        id=job_id,
        name=serialized["name"],
        status=serialized["status"],
        stage=serialized.get("stage"),
        progress=serialized["progress"],
        chunk_count=serialized["chunk_count"],
        processed_chunks=serialized["processed_chunks"],
        text_length=serialized["text_length"],
        error=serialized.get("error"),
        audio_url=serialized.get("audio_url"),
        duration_seconds=serialized.get("duration_seconds"),
        created_at=serialized["created_at"],
        updated_at=serialized["updated_at"]
    )


@app.get("/api/jobs")
async def list_jobs(limit: int = 50, skip: int = 0):
    """List all jobs, most recent first."""
    cursor = db.jobs.find(
        {},
        {"chunks": 0}  # Exclude chunks from list view
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    jobs = []
    async for job in cursor:
        serialized = serialize_doc(job)
        jobs.append({
            "id": serialized["_id"],
            "name": serialized["name"],
            "status": serialized["status"],
            "stage": serialized.get("stage"),
            "progress": serialized["progress"],
            "chunk_count": serialized["chunk_count"],
            "processed_chunks": serialized["processed_chunks"],
            "text_length": serialized["text_length"],
            "error": serialized.get("error"),
            "audio_url": serialized.get("audio_url"),
            "duration_seconds": serialized.get("duration_seconds"),
            "created_at": serialized["created_at"],
            "updated_at": serialized["updated_at"],
            # Lightweight stitching metadata for dashboard tooltip.
            "seed": serialized.get("seed"),
            "model_id": (serialized.get("tts_config") or {}).get("model_id"),
        })
    
    # Get total count
    total = await db.jobs.count_documents({})
    
    return {"jobs": jobs, "total": total}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID."""
    try:
        job = await db.jobs.find_one(
            {"_id": ObjectId(job_id)},
            {"chunks": 0}  # Exclude chunks from response
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    serialized = serialize_doc(job)
    return {
        "id": serialized["_id"],
        "name": serialized["name"],
        "status": serialized["status"],
        "stage": serialized.get("stage"),
        "progress": serialized["progress"],
        "chunk_count": serialized["chunk_count"],
        "processed_chunks": serialized["processed_chunks"],
        "text_length": serialized["text_length"],
        "error": serialized.get("error"),
        "audio_url": serialized.get("audio_url"),
        "duration_seconds": serialized.get("duration_seconds"),
        "created_at": serialized["created_at"],
        "updated_at": serialized["updated_at"]
    }


@app.get("/api/jobs/{job_id}/details")
async def get_job_details(job_id: str):
    """Get full job details including all chunk requests for debugging."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    serialized = serialize_doc(job)
    
    return {
        "id": serialized["_id"],
        "name": serialized["name"],
        "status": serialized["status"],
        "stage": serialized.get("stage"),
        "progress": serialized["progress"],
        "chunk_count": serialized["chunk_count"],
        "processed_chunks": serialized["processed_chunks"],
        "text_length": serialized["text_length"],
        "error": serialized.get("error"),
        "audio_url": serialized.get("audio_url"),
        "duration_seconds": serialized.get("duration_seconds"),
        "created_at": serialized["created_at"],
        "updated_at": serialized["updated_at"],
        "tts_config": serialized.get("tts_config"),
        "chunk_requests": serialized.get("chunk_requests", []),
        "seed": serialized.get("seed"),
        "regenerated_from": serialized.get("regenerated_from"),
    }


@app.get("/api/jobs/{job_id}/download")
async def download_job_audio(job_id: str):
    """Download the audio file for a completed job."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    audio_path = job.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Sanitize filename
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', job["name"])[:50]
    filename = f"{safe_name}.mp3"
    
    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/jobs/{job_id}/chunks/{chunk_index}/audio")
async def get_chunk_audio(job_id: str, chunk_index: int):
    """Stream audio for a specific chunk."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    chunk_requests = job.get("chunk_requests", [])
    if chunk_index < 0 or chunk_index >= len(chunk_requests):
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    chunk = chunk_requests[chunk_index]
    audio_path = chunk.get("audio_path")
    
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Chunk audio file not found")
    
    # Sanitize filename
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', job["name"])[:30]
    filename = f"{safe_name}_chunk_{chunk_index + 1}.mp3"
    
    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=filename
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its audio files (including chunks)."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete main audio file if exists
    audio_path = job.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)
    
    # Delete chunk audio files
    chunk_requests = job.get("chunk_requests", [])
    for chunk in chunk_requests:
        chunk_audio_path = chunk.get("audio_path")
        if chunk_audio_path and os.path.exists(chunk_audio_path):
            try:
                os.remove(chunk_audio_path)
            except:
                pass  # Ignore errors cleaning up chunk files
    
    # Delete from database
    await db.jobs.delete_one({"_id": ObjectId(job_id)})
    
    return {"message": "Job deleted successfully"}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str, background_tasks: BackgroundTasks):
    """
    Retry a failed job from where it left off.
    - For chunking mode: resumes from the first failed/pending chunk
    - For studio mode: restarts the entire job
    """
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] not in ("failed",):
        raise HTTPException(status_code=400, detail=f"Cannot retry job with status '{job['status']}'. Only failed jobs can be retried.")
    
    tts_config = job.get("tts_config", {})
    mode = tts_config.get("mode", "chunking")
    
    if mode == "studio":
        # For studio mode, restart entirely
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "queued",
                "stage": "Retrying...",
                "progress": 0,
                "error": None,
                "updated_at": datetime.utcnow()
            }}
        )
        background_tasks.add_task(process_studio_job, job_id)
        return {"message": "Studio job retry started", "job_id": job_id}
    
    # For chunking mode, resume from failed chunk
    background_tasks.add_task(resume_tts_job, job_id)
    
    return {"message": "Job retry started - resuming from failed chunk", "job_id": job_id}


@app.post("/api/jobs/{job_id}/regenerate", response_model=JobResponse)
async def regenerate_job(job_id: str, background_tasks: BackgroundTasks):
    """
    Create a NEW job from an existing job's source text + TTS config, reusing
    the original `seed` (and, for chunking mode, re-chunking via the same
    rules). This lets the user produce a deterministic re-run of a
    multilingual_v2 job to A/B test prompts/text edits while keeping voice
    identity identical.

    The new job runs through the normal pipeline (background task, webhook,
    Google Drive upload, etc). The source job is left untouched.
    """
    try:
        src = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    if not src:
        raise HTTPException(status_code=404, detail="Job not found")

    src_text: str = src.get("original_text") or ""
    if not src_text:
        # Fallback: stitch chunks back together (legacy jobs may not have
        # original_text stored).
        src_text = "\n\n".join(src.get("chunks", []))
    if not src_text:
        raise HTTPException(status_code=400, detail="Source job has no text to regenerate from")

    tts_config = src.get("tts_config", {}) or {}
    mode = tts_config.get("mode", "chunking")
    model_id = tts_config.get("model_id", ELEVENLABS_MODEL)
    voice_settings = tts_config.get("voice_settings", DEFAULT_TTS_SETTINGS["voice_settings"])
    studio_settings = tts_config.get("studio_settings", DEFAULT_TTS_SETTINGS["studio_settings"])
    pronunciation_dict = tts_config.get("pronunciation_dictionary")

    # Re-chunk using the same rules and the source job's chunk_size.
    if mode == "chunking":
        chunk_size = tts_config.get("chunk_size") or DEFAULT_CHUNK_SIZE
        if model_id == MODEL_MULTILINGUAL_V2:
            chunks = split_text_into_chunks_v2(src_text, hard_cap=chunk_size)
        else:
            chunks = split_text_into_chunks(src_text, max_chars=chunk_size)
        if not chunks:
            raise HTTPException(status_code=400, detail="Source text is too short to process")
        chunk_count = len(chunks)
    else:
        chunks = [src_text]
        chunk_count = 1

    # Reuse the source seed when present (multilingual_v2 deterministic re-run).
    # If the source has no seed but the new run will be multilingual_v2 chunking,
    # mint a fresh one so the new chain is still stitched.
    job_seed: Optional[int] = src.get("seed")
    if job_seed is None and mode == "chunking" and model_id == MODEL_MULTILINGUAL_V2:
        job_seed = random.randint(0, 2**31 - 1)

    chunk_requests = []
    for i, chunk_text in enumerate(chunks):
        if mode == "chunking":
            chunk_requests.append({
                "chunk_index": i,
                "request": {
                    "endpoint": "POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    "voice_id": tts_config.get("voice_id", ELEVENLABS_VOICE_ID),
                    "model_id": model_id,
                    "output_format": tts_config.get("output_format", "mp3_44100_128"),
                    "voice_settings": voice_settings,
                    "pronunciation_dictionary_locators": [pronunciation_dict] if pronunciation_dict and pronunciation_dict.get("pronunciation_dictionary_id") else None,
                    "text": chunk_text,
                    "text_length": len(chunk_text),
                },
                "status": "pending",
                "processed_at": None,
            })
        else:
            chunk_requests.append({
                "chunk_index": i,
                "request": {
                    "endpoint": "POST https://api.elevenlabs.io/v1/studio/projects",
                    "voice_id": tts_config.get("voice_id", ELEVENLABS_VOICE_ID),
                    "model_id": model_id,
                    "quality_preset": studio_settings.get("quality_preset", "standard"),
                    "voice_settings": voice_settings,
                    "studio_settings": studio_settings,
                    "text_length": len(chunk_text),
                },
                "status": "pending",
                "processed_at": None,
            })

    now = datetime.utcnow()
    new_doc = {
        "name": f"{src.get('name', 'job')} (regen)",
        "text_length": len(src_text),
        "original_text": src_text,
        "chunk_count": chunk_count,
        "processed_chunks": 0,
        "chunks": chunks,
        "chunk_requests": chunk_requests,
        "external_job_id": src.get("external_job_id"),
        "files_url": src.get("files_url"),
        "callback_data": src.get("callback_data"),
        "folder_id": src.get("folder_id"),
        "seed": job_seed,
        "regenerated_from": str(src["_id"]),  # provenance link
        "tts_config": {
            "api": tts_config.get("api", "ElevenLabs"),
            "mode": mode,
            "voice_id": tts_config.get("voice_id", ELEVENLABS_VOICE_ID),
            "model_id": model_id,
            "output_format": tts_config.get("output_format", "mp3_44100_128"),
            "chunk_size": tts_config.get("chunk_size") if mode == "chunking" else None,
            "pronunciation_dictionary": pronunciation_dict,
            "voice_settings": voice_settings,
            "studio_settings": studio_settings,
        },
        "status": "queued",
        "stage": "Waiting in queue...",
        "progress": 0,
        "error": None,
        "audio_path": None,
        "audio_url": None,
        "duration_seconds": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.jobs.insert_one(new_doc)
    new_job_id = str(result.inserted_id)

    if mode == "studio":
        background_tasks.add_task(process_studio_job, new_job_id)
    else:
        background_tasks.add_task(process_tts_job, new_job_id)

    new_doc["_id"] = result.inserted_id
    serialized = serialize_doc(new_doc)
    return JobResponse(
        id=new_job_id,
        name=serialized["name"],
        status=serialized["status"],
        stage=serialized.get("stage"),
        progress=serialized["progress"],
        chunk_count=serialized["chunk_count"],
        processed_chunks=serialized["processed_chunks"],
        text_length=serialized["text_length"],
        error=serialized.get("error"),
        audio_url=serialized.get("audio_url"),
        duration_seconds=serialized.get("duration_seconds"),
        created_at=serialized["created_at"],
        updated_at=serialized["updated_at"],
    )


async def resume_tts_job(job_id: str):
    """Resume a failed TTS job from the first incomplete chunk."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            print(f"Job {job_id} not found for resume")
            return
        
        tts_settings = job.get("tts_config", DEFAULT_TTS_SETTINGS)
        chunks = job["chunks"]
        chunk_count = len(chunks)
        chunk_requests = job.get("chunk_requests", [])
        
        # Find first incomplete chunk
        start_chunk = 0
        for i, cr in enumerate(chunk_requests):
            if cr.get("status") == "completed" and cr.get("audio_path") and os.path.exists(cr.get("audio_path", "")):
                start_chunk = i + 1
            else:
                break
        
        print(f"Resuming job {job_id} from chunk {start_chunk + 1}/{chunk_count}")
        
        # Update job status
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "transcribing",
                "stage": f"Resuming from chunk {start_chunk + 1}...",
                "error": None,
                "updated_at": datetime.utcnow()
            },
            "$unset": {"failed_at_chunk": ""}}
        )
        
        # Initialize ElevenLabs client
        eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Request-stitching state (only multilingual_v2).
        model_id = tts_settings.get("model_id", ELEVENLABS_MODEL)
        stitching_enabled = (model_id == MODEL_MULTILINGUAL_V2)
        job_seed: Optional[int] = job.get("seed") if stitching_enabled else None
        request_ids: list = []
        if stitching_enabled:
            # Rebuild request_ids list from already-completed chunks so the next
            # chunk continues the stitching chain.
            for cr in chunk_requests[:start_chunk]:
                rid = cr.get("request_id")
                if rid:
                    request_ids.append(rid)
            print(f"Job {job_id} resume: stitching ON (seed={job_seed}, "
                  f"recovered {len(request_ids)} prior request_ids)")
        
        # Load existing audio chunks
        audio_chunks = []
        for i in range(start_chunk):
            chunk_audio_path = os.path.join(STORAGE_DIR, f"{job_id}_chunk_{i}.mp3")
            if os.path.exists(chunk_audio_path):
                with open(chunk_audio_path, "rb") as f:
                    audio_chunks.append(f.read())
            else:
                print(f"Warning: Missing audio for chunk {i}, will reprocess")
                start_chunk = min(start_chunk, i)
                audio_chunks = audio_chunks[:i]
                break
        
        # Process remaining chunks
        for i in range(start_chunk, chunk_count):
            chunk_text = chunks[i]
            print(f"Processing chunk {i + 1}/{chunk_count} for job {job_id} (resume)")
            
            # Update chunk status to processing
            await db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    f"chunk_requests.{i}.status": "processing",
                    "updated_at": datetime.utcnow()
                }}
            )
            
            try:
                prev_ids = request_ids[-V2_MAX_PREVIOUS_REQUEST_IDS:] if stitching_enabled and request_ids else None
                audio_data, chunk_request_id = await tts_chunk_with_retry(
                    eleven_client, chunk_text, tts_settings, i, job_id,
                    seed=job_seed,
                    previous_request_ids=prev_ids,
                )
                audio_chunks.append(audio_data)
                if stitching_enabled and chunk_request_id:
                    request_ids.append(chunk_request_id)
                
                # Save individual chunk audio file
                chunk_audio_path = os.path.join(STORAGE_DIR, f"{job_id}_chunk_{i}.mp3")
                with open(chunk_audio_path, "wb") as f:
                    f.write(audio_data)
                
                # Update progress
                progress = int(((i + 1) / chunk_count) * 85)
                chunk_update = {
                    "processed_chunks": i + 1,
                    "progress": progress,
                    "stage": f"Converting to speech ({i + 1}/{chunk_count})...",
                    "updated_at": datetime.utcnow(),
                    f"chunk_requests.{i}.status": "completed",
                    f"chunk_requests.{i}.processed_at": datetime.utcnow().isoformat(),
                    f"chunk_requests.{i}.audio_path": chunk_audio_path,
                    f"chunk_requests.{i}.audio_url": f"/api/jobs/{job_id}/chunks/{i}/audio",
                }
                if stitching_enabled:
                    chunk_update[f"chunk_requests.{i}.request_id"] = chunk_request_id
                    chunk_update[f"chunk_requests.{i}.previous_request_ids"] = prev_ids or []
                    chunk_update[f"chunk_requests.{i}.seed"] = job_seed
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": chunk_update}
                )
            except Exception as e:
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            f"chunk_requests.{i}.status": "failed",
                            f"chunk_requests.{i}.error": str(e),
                            "failed_at_chunk": i,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                print(f"Resume failed at chunk {i + 1}: {e}")
                return
        
        # Merge audio chunks
        print(f"Merging {len(audio_chunks)} audio chunks for job {job_id}")
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "merging", "stage": "Merging audio chunks...", "progress": 90, "updated_at": datetime.utcnow()}}
        )
        
        merged_audio, duration = await asyncio.to_thread(
            merge_audio_chunks, audio_chunks
        )
        
        # Save merged file
        audio_path = os.path.join(STORAGE_DIR, f"{job_id}.mp3")
        with open(audio_path, "wb") as f:
            f.write(merged_audio)
        
        # Upload to Google Drive if folder_id provided
        google_drive_url = None
        google_drive_file_id = None
        folder_id = job.get("folder_id")
        if folder_id:
            print(f"Uploading to Google Drive folder: {folder_id}")
            file_name = f"{job.get('name', 'audio')}_{job_id}.mp3"
            drive_result = upload_to_google_drive(audio_path, folder_id, file_name)
            if drive_result:
                google_drive_url = drive_result.get('web_view_link')
                google_drive_file_id = drive_result.get('file_id')
                print(f"Google Drive upload successful: {google_drive_file_id}")
        
        # Update job as completed
        audio_url = f"/api/jobs/{job_id}/download"
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "progress": 100,
                    "stage": "Complete",
                    "audio_path": audio_path,
                    "audio_url": audio_url,
                    "duration_seconds": duration,
                    "google_drive_url": google_drive_url,
                    "google_drive_file_id": google_drive_file_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"Resumed job {job_id} completed. Duration: {duration:.2f}s")
        
        # Send webhook
        full_audio_url = f"{APP_DOMAIN}{audio_url}"
        await send_webhook(
            job_id=job_id,
            name=job["name"],
            audio_url=full_audio_url,
            status="completed",
            text_length=job["text_length"],
            chunk_count=chunk_count,
            external_job_id=job.get("external_job_id"),
            files_url=job.get("files_url"),
            callback_data=job.get("callback_data"),
            google_drive_url=google_drive_url,
            google_drive_file_id=google_drive_file_id
        )
        
    except Exception as e:
        print(f"Error resuming job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.utcnow()}}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
