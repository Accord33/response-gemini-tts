from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from fastapi.responses import FileResponse

import io
import os
import wave
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
    """PCMデータをWaveファイルフォーマット(bytes)にパックして返す。"""
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

def generate_audio(client: Client, content: str, speakers: list[SpeakerSetting]) -> bytes:
    voice_response = client.models.generate_content(
        model='gemini-2.5-flash-preview-tts',
        contents=content,
        config=types.GenerateContentConfig(
            response_modalities=['AUDIO'],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker=s.speaker,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=s.voice_name,
                                )
                            ),
                        )
                        for s in speakers
                    ]
                )
            ),
        ),
    )

    candidates = voice_response.candidates
    if (
        candidates and candidates[0].content and
        candidates[0].content.parts and
        candidates[0].content.parts[0].inline_data
    ):
        data: bytes = candidates[0].content.parts[0].inline_data.data
    else:
        raise ValueError('APIから音声データが受信されませんでした。')

    if not data:
        raise ValueError('APIから音声データが受信されませんでした。')

    return data

def build_wav_from_prompt(content: str) -> bytes:
    client = Client(api_key=os.getenv('GEMINI_API_KEY'))
    pcm_bytes = generate_audio(
        client,
        content,
        speakers=[
            SpeakerSetting(speaker='A', voice_name='Leda'),
            SpeakerSetting(speaker='B', voice_name='Gacrux'),
        ],
    )
    wav = wave_bytes(pcm_bytes, channels=1, rate=24000, sample_width=2)
    
    # test.wavファイルに書き込み
    with open('output.wav', 'wb') as f:
        f.write(wav)
    
    return wav

app = FastAPI()

class InputData(BaseModel):
    prompt: str
    content: str

# --- JSON 専用(動作確認用) ---
@app.post("/api/ping")
async def ping():
    return JSONResponse({"result": "pong"})

# --- WAV バイナリ専用（Dify のファイル出力用） ---
audio_binary_response = {
    200: {
        "description": "Generated WAV audio",
        "content": {
            "audio/wav": {
                "schema": {"type": "string", "format": "binary"}
            }
        }
    },
    400: {"description": "Bad Request"},
    500: {"description": "Internal Server Error"},
}

AUDIO_PATH = "./output.wav"

@app.post("/audio", responses=audio_binary_response)
async def audio(data: InputData = Body(...)):
    try:
        if not data.content:
            raise HTTPException(status_code=400, detail="content is required")
        
        print(data.prompt)

        wav_bytes = build_wav_from_prompt(data.prompt)
        
        # Dify/クライアントが確実に「ファイル」として扱うよう attachment を推奨
        print("生成終了：ファイル送信開始")
        return FileResponse(
            path=str(AUDIO_PATH),
            media_type="audio/wav",
            filename=AUDIO_PATH,                  # Content-Disposition: attachment; filename="..."
            headers={"Cache-Control": "no-store"}      # 任意：キャッシュ抑止
        )

    except HTTPException:
        raise
    except Exception as e:
        # ログ出力のみ簡略
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
