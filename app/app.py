from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

import io
import os
import wave
import asyncio
from dataclasses import dataclass

from dotenv import load_dotenv
from google.genai import Client, types

load_dotenv()

def wave_bytes(
    pcm: bytes,
    channels: int = 1,
    rate: int = 24000,
    sample_width: int = 2,
) -> bytes:
    """PCM を WAVE バイナリに変換"""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


@dataclass(frozen=True)
class SpeakerSetting:
    speaker: str
    voice_name: str


def generate_audio_sync(content: str) -> bytes:
    """
    Gemini TTS 同期版（ブロッキング）
    → run_in_executor でスレッドに逃がして非同期化する
    """
    client = Client(api_key=os.getenv("GEMINI_API_KEY"))

    voice_response = client.models.generate_content(
        model='gemini-2.5-flash-preview-tts',
        contents=content,
        config=types.GenerateContentConfig(
            response_modalities=['AUDIO'],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker='A',
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name='Leda'
                                )
                            )
                        ),
                        types.SpeakerVoiceConfig(
                            speaker='B',
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name='Gacrux'
                                )
                            )
                        )
                    ]
                )
            ),
        ),
    )

    parts = voice_response.candidates[0].content.parts
    if not parts or not parts[0].inline_data:
        raise RuntimeError("音声データが取得できませんでした")

    pcm = parts[0].inline_data.data

    # PCM → WAV
    return wave_bytes(pcm)


async def generate_audio_async(content: str) -> bytes:
    """
    ブロッキング処理を event loop から切り離す
    FastAPI / asyncio を止めない
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, generate_audio_sync, content)


app = FastAPI()


class InputData(BaseModel):
    prompt: str
    content: str


@app.post("/audio")
async def audio(data: InputData = Body(...)):
    if not data.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    try:
        # 非同期で音声生成（バックグラウンドスレッドで実行される）
        wav_bytes = await generate_audio_async(data.prompt)

        # BytesIO から直接 StreamingResponse を返す（ファイル保存なし）
        return StreamingResponse(
            io.BytesIO(wav_bytes),
            media_type="audio/wav",
            headers={"Cache-Control": "no-store"},
        )

    except Exception as e:
        print("[ERROR]", e)
        raise HTTPException(status_code=500, detail=str(e))