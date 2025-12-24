"""
Text-to-Speech Chunker Backend
FastAPI server for processing long texts into speech using ElevenLabs API
"""

import os
import re
import asyncio
import httpx
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
from pydub import AudioSegment
from elevenlabs import ElevenLabs

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
MAX_CHUNK_SIZE = 10000  # ElevenLabs v3 max characters per request

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


async def tts_chunk_to_audio(client: ElevenLabs, text: str) -> bytes:
    """
    Convert text chunk to audio using ElevenLabs TTS API.
    Returns MP3 bytes.
    """
    # Use the text_to_speech.convert method from the SDK
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=ELEVENLABS_VOICE_ID,
        model_id=ELEVENLABS_MODEL,
        output_format="mp3_44100_128"  # High quality MP3
    )
    
    # Collect all audio bytes from generator
    audio_data = b""
    for chunk in audio_generator:
        audio_data += chunk
    
    return audio_data


def merge_audio_chunks(audio_chunks: list[bytes]) -> tuple[bytes, float]:
    """
    Merge multiple MP3 audio chunks into a single MP3 file.
    Returns (merged_bytes, duration_seconds)
    """
    combined = None
    
    for chunk_bytes in audio_chunks:
        segment = AudioSegment.from_mp3(BytesIO(chunk_bytes))
        if combined is None:
            combined = segment
        else:
            combined = combined + segment
    
    if combined is None:
        raise ValueError("No audio chunks to merge")
    
    # Export to MP3 bytes
    output_buffer = BytesIO()
    combined.export(output_buffer, format="mp3", bitrate="128k")
    output_buffer.seek(0)
    
    duration_seconds = len(combined) / 1000.0
    return output_buffer.read(), duration_seconds


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


async def process_tts_job(job_id: str):
    """Background task to process TTS job."""
    try:
        # Get job from database
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            print(f"Job {job_id} not found")
            return
        
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
                    lambda ct=chunk_text: tts_chunk_to_audio_sync(eleven_client, ct)
                )
                audio_chunks.append(audio_data)
                
                # Update progress
                progress = int(((i + 1) / chunk_count) * 85)  # 85% for TTS, 15% for merge
                await db.jobs.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            "processed_chunks": i + 1,
                            "progress": progress,
                            "stage": f"Converting to speech ({i + 1}/{chunk_count})...",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            except Exception as e:
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
        frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "https://speech-chunk-builder.preview.emergentagent.com")
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


def tts_chunk_to_audio_sync(client: ElevenLabs, text: str) -> bytes:
    """Synchronous version of TTS conversion."""
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=ELEVENLABS_VOICE_ID,
        model_id=ELEVENLABS_MODEL,
        output_format="mp3_44100_128"
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


@app.post("/api/jobs", response_model=JobResponse)
async def create_job(job_data: JobCreate, background_tasks: BackgroundTasks):
    """Create a new TTS job."""
    # Chunk the text
    chunks = split_text_into_chunks(job_data.text)
    
    if len(chunks) == 0:
        raise HTTPException(status_code=400, detail="Text is too short to process")
    
    # Create job document
    now = datetime.utcnow()
    job_doc = {
        "name": job_data.name,
        "text_length": len(job_data.text),
        "chunk_count": len(chunks),
        "processed_chunks": 0,
        "chunks": chunks,
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
    
    # Start background processing
    background_tasks.add_task(process_tts_job, job_id)
    
    # Return response
    job_doc["_id"] = result.inserted_id
    serialized = serialize_doc(job_doc)
    
    return JobResponse(
        id=job_id,
        name=serialized["name"],
        status=serialized["status"],
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


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its audio file."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete audio file if exists
    audio_path = job.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)
    
    # Delete from database
    await db.jobs.delete_one({"_id": ObjectId(job_id)})
    
    return {"message": "Job deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
