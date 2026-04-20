import speech_recognition as sr
from pydub import AudioSegment
import os

def convert_to_wav(file_path: str) -> str:
    """
    오디오 파일을 wav로 변환합니다. 이미 wav라면 그대로 반환합니다.
    m4a, mp3, webm 등 ffmpeg이 지원하는 모든 포맷을 처리합니다.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".wav":
        return file_path
        
    wav_path = os.path.splitext(file_path)[0] + "_converted.wav"
    try:
        print(f"Converting {file_path} to wav...")
        # m4a, mp3 등을 읽어오기 위해 pydub와 ffmpeg 사용
        if ext == ".m4a":
            audio = AudioSegment.from_file(file_path, format="m4a")
        else:
            audio = AudioSegment.from_file(file_path)
            
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"Conversion error for {ext} (ffmpeg might be required): {e}")
        return None

async def transcribe_audio(file_path: str) -> str:
    # 1. 필요 시 변환 시도 (.m4a 등 포함)
    processing_path = convert_to_wav(file_path)
    
    if not processing_path or not os.path.exists(processing_path):
        return f"[인식 실패] {os.path.splitext(file_path)[1]} 형식을 처리할 수 없습니다. ffmpeg 설치 여부를 확인하세요."
    
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(processing_path) as source:
            # 배경 소음 감소 (필요 시)
            # recognizer.adjust_for_ambient_noise(source)
            audio_data = recognizer.record(source)
            # 2. Google Web Speech API 사용
            text = recognizer.recognize_google(audio_data, language="ko-KR")
            return text
    except sr.UnknownValueError:
        return "[인식 실패] 음성을 이해할 수 없습니다."
    except sr.RequestError as e:
        return f"[서비스 오류] {e}"
    except Exception as e:
        return f"[시스템 오류] {e}"
    finally:
        # 변환된 임시 파일이 생성되었다면 삭제
        if processing_path != file_path and os.path.exists(processing_path):
            try:
                os.remove(processing_path)
            except:
                pass
