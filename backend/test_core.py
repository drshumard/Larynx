"""
POC Test Script: ElevenLabs TTS Chunking + Audio Merge + Webhook
Tests:
1. Sentence-boundary text chunking (max 10,000 chars per chunk)
2. ElevenLabs TTS API v3 calls
3. MP3 concatenation
4. Webhook delivery
"""

import os
import re
import httpx
from io import BytesIO
from pydub import AudioSegment
from elevenlabs import ElevenLabs

# Configuration
ELEVENLABS_API_KEY = "sk_e80ab01e82f120260468d7955899f07b10ef028fdbc6a564"
VOICE_ID = "LNHBM9NjjOl44Efsdmtl"
MODEL_ID = "eleven_multilingual_v2"  # ElevenLabs v3 model
WEBHOOK_URL = "https://drshumard.app.n8n.cloud/webhook/cb298a5c-abcf-4596-bec3-e457f0798790"
MAX_CHUNK_SIZE = 10000  # 10,000 characters max per TTS request

# Storage
STORAGE_DIR = "/app/backend/storage"
os.makedirs(STORAGE_DIR, exist_ok=True)


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


def tts_chunk_to_audio(client: ElevenLabs, text: str) -> bytes:
    """
    Convert text chunk to audio using ElevenLabs TTS API.
    Returns MP3 bytes.
    """
    print(f"  -> TTS converting {len(text)} characters...")
    
    # Use the text_to_speech.convert method from the SDK
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        output_format="mp3_44100_128"  # High quality MP3
    )
    
    # Collect all audio bytes from generator
    audio_data = b""
    for chunk in audio_generator:
        audio_data += chunk
    
    print(f"  -> Received {len(audio_data)} bytes of audio")
    return audio_data


def merge_audio_chunks(audio_chunks: list[bytes]) -> bytes:
    """
    Merge multiple MP3 audio chunks into a single MP3 file.
    Uses pydub for proper audio concatenation.
    """
    print(f"\n[MERGE] Combining {len(audio_chunks)} audio chunks...")
    
    combined = None
    
    for i, chunk_bytes in enumerate(audio_chunks):
        print(f"  -> Processing chunk {i + 1}/{len(audio_chunks)}")
        
        # Load audio segment from bytes
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
    
    print(f"  -> Final duration: {len(combined) / 1000:.2f} seconds")
    return output_buffer.read()


def send_webhook(job_id: str, name: str, audio_url: str, status: str, text_len: int, chunk_count: int) -> bool:
    """
    Send webhook notification on job completion.
    """
    print(f"\n[WEBHOOK] Sending to {WEBHOOK_URL}...")
    
    payload = {
        "jobId": job_id,
        "name": name,
        "audioUrl": audio_url,
        "status": status,
        "textLength": text_len,
        "chunkCount": chunk_count
    }
    
    try:
        response = httpx.post(WEBHOOK_URL, json=payload, timeout=10.0)
        print(f"  -> Status: {response.status_code}")
        print(f"  -> Response: {response.text[:200] if response.text else 'empty'}")
        return response.status_code in (200, 201, 202, 204)
    except Exception as e:
        print(f"  -> Error: {e}")
        return False


def run_poc():
    """
    Run the complete POC test.
    """
    print("=" * 60)
    print("POC: ElevenLabs TTS Chunking + Audio Merge + Webhook")
    print("=" * 60)
    
    # Create test text that spans multiple chunks (slightly over 10k chars to force 2 chunks)
    base_sentence = "This is a test sentence for the text to speech conversion system. "
    # Each sentence is ~70 chars, we need ~150 sentences to get ~10,500 chars for 2 chunks
    test_text = base_sentence * 160  # ~11,200 chars - should result in 2 chunks
    
    print(f"\n[INPUT] Test text length: {len(test_text)} characters")
    
    # Step 1: Chunk the text
    print("\n[STEP 1] Chunking text at sentence boundaries...")
    chunks = split_text_into_chunks(test_text)
    print(f"  -> Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"     Chunk {i + 1}: {len(chunk)} characters")
    
    # Step 2: Initialize ElevenLabs client
    print("\n[STEP 2] Initializing ElevenLabs client...")
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    
    # Step 3: Convert each chunk to audio
    print("\n[STEP 3] Converting chunks to audio...")
    audio_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"\n  Chunk {i + 1}/{len(chunks)}:")
        try:
            audio_data = tts_chunk_to_audio(client, chunk)
            audio_chunks.append(audio_data)
        except Exception as e:
            print(f"  -> ERROR: {e}")
            raise
    
    print(f"\n  -> Successfully converted {len(audio_chunks)} chunks")
    
    # Step 4: Merge audio chunks
    print("\n[STEP 4] Merging audio chunks...")
    try:
        final_audio = merge_audio_chunks(audio_chunks)
        print(f"  -> Final audio size: {len(final_audio)} bytes")
    except Exception as e:
        print(f"  -> ERROR merging: {e}")
        raise
    
    # Step 5: Save to file
    output_path = os.path.join(STORAGE_DIR, "poc_combined.mp3")
    print(f"\n[STEP 5] Saving to {output_path}...")
    with open(output_path, "wb") as f:
        f.write(final_audio)
    print(f"  -> Saved! File size: {os.path.getsize(output_path)} bytes")
    
    # Verify audio is valid
    try:
        audio = AudioSegment.from_mp3(output_path)
        print(f"  -> Audio duration: {len(audio) / 1000:.2f} seconds")
        print(f"  -> Channels: {audio.channels}")
        print(f"  -> Sample rate: {audio.frame_rate} Hz")
    except Exception as e:
        print(f"  -> WARNING: Could not verify audio: {e}")
    
    # Step 6: Test webhook
    print("\n[STEP 6] Testing webhook delivery...")
    webhook_success = send_webhook(
        job_id="poc_test_001",
        name="POC Test User",
        audio_url=f"http://localhost:8001/api/download/poc_combined.mp3",
        status="completed",
        text_len=len(test_text),
        chunk_count=len(chunks)
    )
    
    # Summary
    print("\n" + "=" * 60)
    print("POC RESULTS:")
    print("=" * 60)
    print(f"  ✓ Text chunking: {len(chunks)} chunks created")
    print(f"  ✓ TTS conversion: {len(audio_chunks)} audio segments")
    print(f"  ✓ Audio merge: {len(final_audio)} bytes")
    print(f"  ✓ File saved: {output_path}")
    print(f"  {'✓' if webhook_success else '✗'} Webhook: {'delivered' if webhook_success else 'failed'}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    run_poc()
