import os
import webbrowser
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from groq import Groq

from dotenv import load_dotenv
assert load_dotenv("key.env")

app = FastAPI()
client = Groq(api_key=os.environ["GROK"])
PRESET_URL = "https://www.google.com" # 원하는 URL로 변경해주세요

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/upload-audio/")
async def process_audio(file: UploadFile = File(...)):
    file_location = f"temp_{file.filename}"
    
    # 1. 로컬 저장소에 녹음 파일 저장
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    # 2. 저장된 파일을 읽어 Groq API에 전송
    with open(file_location, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(file_location, audio_file.read()),
            model="whisper-large-v3",
            response_format="json",
            language="ko",
        )
    
    # 처리 후 로컬 임시 파일 삭제
    os.remove(file_location) 
    text = transcription.text
    
    # 3. 결과에 따른 동작 결정
    if "로그인" in text:
        webbrowser.open(PRESET_URL)
        return {"message": f"'{text}' 인식됨: 설정된 URL을 열었습니다."}
    else:
        return {"message": f"'{text}' 인식됨: 재시도 해주세요."}