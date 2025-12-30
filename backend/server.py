"""
Text-to-Speech Chunker Backend
FastAPI server for processing long texts into speech using ElevenLabs API
"""

import os
import re
import asyncio
import httpx
import subprocess
import tempfile
from io import BytesIO
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from elevenlabs import ElevenLabs

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
STORAGE_DIR = "/app/backend/storage"

# Debug: Print API key status
print(f"ElevenLabs API Key loaded: {'Yes' if ELEVENLABS_API_KEY else 'No'}")

# Constants
MAX_CHUNK_SIZE = 4500  # ElevenLabs eleven_v3 max is 5000 chars, using 4500 for safety

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
    voice_settings: VoiceSettings = Field(default_factory=VoiceSettings)
    studio_settings: StudioSettings = Field(default_factory=StudioSettings)


class TTSSettingsUpdate(BaseModel):
    mode: Optional[str] = None
    voice_id: Optional[str] = None
    model_id: Optional[str] = None
    output_format: Optional[str] = None
    voice_settings: Optional[VoiceSettings] = None
    studio_settings: Optional[StudioSettings] = None


# Default TTS settings
DEFAULT_TTS_SETTINGS = {
    "mode": "chunking",
    "voice_id": ELEVENLABS_VOICE_ID,
    "model_id": ELEVENLABS_MODEL,
    "output_format": "mp3_44100_128",
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


def split_text_into_chunks(text: str, max_chars: int = MAX_CHUNK_SIZE) -> list[str]:
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


async def tts_chunk_to_audio(client: ElevenLabs, text: str, settings: dict) -> bytes:
    """
    Convert text chunk to audio using ElevenLabs TTS API.
    Returns MP3 bytes.
    """
    voice_settings = settings.get("voice_settings", {})
    
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
        }
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


async def send_webhook(job_id: str, name: str, audio_url: str, status: str, text_length: int, chunk_count: int):
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
    
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(WEBHOOK_URL, json=payload, timeout=10.0)
            print(f"Webhook sent: {response.status_code}")
            return response.status_code in (200, 201, 202, 204)
    except Exception as e:
        print(f"Webhook error: {e}")
        return False


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
                    "updated_at": datetime.utcnow()
                }}
            )
            
            print(f"Studio job {job_id} completed. Duration: {duration}s")
            
            # Send webhook notification
            if WEBHOOK_URL:
                await send_webhook(
                    job_id=job_id,
                    name=job.get("name"),
                    audio_url=audio_url,
                    status="completed",
                    text_length=len(text),
                    chunk_count=1
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
        
        # Update status to transcribing
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "transcribing", "stage": f"Converting to speech (0/{chunk_count})...", "updated_at": datetime.utcnow()}}
        )
        
        # Process each chunk
        for i, chunk_text in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{chunk_count} for job {job_id}")
            
            try:
                audio_data = await asyncio.to_thread(
                    lambda ct=chunk_text, s=tts_settings: tts_chunk_to_audio_sync(eleven_client, ct, s)
                )
                audio_chunks.append(audio_data)
                
                # Save individual chunk audio file
                chunk_audio_path = os.path.join(STORAGE_DIR, f"{job_id}_chunk_{i}.mp3")
                with open(chunk_audio_path, "wb") as f:
                    f.write(audio_data)
                
                # Update progress and chunk request status
                progress = int(((i + 1) / chunk_count) * 85)  # 85% for TTS, 15% for merge
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            "processed_chunks": i + 1,
                            "progress": progress,
                            "stage": f"Converting to speech ({i + 1}/{chunk_count})...",
                            "updated_at": datetime.utcnow(),
                            f"chunk_requests.{i}.status": "completed",
                            f"chunk_requests.{i}.processed_at": datetime.utcnow().isoformat(),
                            f"chunk_requests.{i}.audio_path": chunk_audio_path,
                            f"chunk_requests.{i}.audio_url": f"/api/jobs/{job_id}/chunks/{i}/audio"
                        }
                    }
                )
            except Exception as e:
                # Mark chunk as failed
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            f"chunk_requests.{i}.status": "failed",
                            f"chunk_requests.{i}.error": str(e),
                            f"chunk_requests.{i}.processed_at": datetime.utcnow().isoformat()
                        }
                    }
                )
                print(f"Error processing chunk {i + 1}: {e}")
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
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"Job {job_id} completed. Duration: {duration:.2f}s")
        
        # Send webhook
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "https://audio-genie-5.preview.emergentagent.com")
        full_audio_url = f"{frontend_url}{audio_url}"
        await send_webhook(
            job_id=job_id,
            name=job["name"],
            audio_url=full_audio_url,
            status="completed",
            text_length=job["text_length"],
            chunk_count=chunk_count
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


def tts_chunk_to_audio_sync(client: ElevenLabs, text: str, settings: dict) -> bytes:
    """Synchronous version of TTS conversion."""
    voice_settings = settings.get("voice_settings", {})
    
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
        }
    )
    
    audio_data = b""
    for chunk in audio_generator:
        audio_data += chunk
    
    return audio_data


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
    settings_dict = {
        "mode": settings.mode,
        "voice_id": settings.voice_id,
        "model_id": settings.model_id,
        "output_format": settings.output_format,
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
        chunks = split_text_into_chunks(job_data.text)
        if len(chunks) == 0:
            raise HTTPException(status_code=400, detail="Text is too short to process")
        chunk_count = len(chunks)
    else:
        # Studio mode - single "chunk" containing all text
        chunks = [job_data.text]
        chunk_count = 1
    
    chunk_requests = []
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
    job_doc = {
        "name": job_data.name,
        "text_length": len(job_data.text),
        "original_text": job_data.text,  # Store original text for Studio mode
        "chunk_count": chunk_count,
        "processed_chunks": 0,
        "chunks": chunks,
        "chunk_requests": chunk_requests,
        "tts_config": {
            "api": "ElevenLabs",
            "mode": mode,
            "voice_id": tts_settings.get("voice_id", ELEVENLABS_VOICE_ID),
            "model_id": tts_settings.get("model_id", ELEVENLABS_MODEL),
            "output_format": tts_settings.get("output_format", "mp3_44100_128"),
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
            "updated_at": serialized["updated_at"]
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
        "chunk_requests": serialized.get("chunk_requests", [])
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
