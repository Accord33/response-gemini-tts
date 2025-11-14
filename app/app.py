from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import io
import os
import wave
import asyncio
import tempfile
import logging
from dataclasses import dataclass

from dotenv import load_dotenv
from google.genai import Client, types

load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    logger.info(f"音声生成開始: {content[:50]}...")
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
    logger.info(f"PCMデータ取得成功: {len(pcm)} bytes")

    # PCM → WAV
    wav_data = wave_bytes(pcm)
    logger.info(f"WAV変換完了: {len(wav_data)} bytes")
    return wav_data


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
        logger.info("リクエスト受信: /audio")
        # 非同期で音声生成（バックグラウンドスレッドで実行される）
        wav_bytes = await generate_audio_async(data.prompt)

        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(wav_bytes)
            tmp_path = tmp_file.name
        
        logger.info(f"一時ファイル作成: {tmp_path}")

        # ファイルレスポンスを返す
        logger.info(f"ファイルレスポンス返却: {tmp_path}")
        return FileResponse(
            tmp_path,
            media_type="audio/wav",
            filename="audio.wav"
        )

    except Exception as e:
        logger.error(f"エラー発生: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))