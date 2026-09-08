import os
import wave
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from groq import Groq
from faster_whisper import WhisperModel
from piper import PiperVoice

from personalities import PERSONALITIES

load_dotenv()

SAMPLE_RATE = 16000
RECORD_SECONDS = 5
LLM_MODEL = "llama-3.3-70b-versatile"

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

print("Loading speech-to-text model (first run downloads it, ~140MB)...")
whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")

_voice_cache = {}


def get_voice(personality):
    if personality not in _voice_cache:
        _voice_cache[personality] = PiperVoice.load(PERSONALITIES[personality]["voice_file"])
    return _voice_cache[personality]


def record_audio():
    print(f"\nRecording for {RECORD_SECONDS} seconds - speak now...")
    audio = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return audio


def save_wav(audio, path="_temp_input.wav"):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return path


def transcribe(path):
    segments, _ = whisper_model.transcribe(path)
    return "".join(seg.text for seg in segments).strip()


def get_reply(personality, history, user_text):
    history.append({"role": "user", "content": user_text})
    messages = [{"role": "system", "content": PERSONALITIES[personality]["system_prompt"]}] + history
    response = groq_client.chat.completions.create(model=LLM_MODEL, messages=messages)
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return reply


def speak(personality, text):
    voice = get_voice(personality)
    stream = None
    for chunk in voice.synthesize(text):
        if stream is None:
            stream = sd.OutputStream(samplerate=chunk.sample_rate, channels=chunk.sample_channels, dtype="int16")
            stream.start()
        stream.write(np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16))
    if stream:
        stream.stop()
        stream.close()


def choose_personality():
    options = list(PERSONALITIES.keys())
    print("Choose a personality:", ", ".join(options))
    while True:
        choice = input("> ").strip().lower()
        if choice in options:
            return choice
        print(f"Not one of {options}, try again.")


def main():
    personality = choose_personality()
    history = []
    print(f"\nAurora is ready in '{personality}' mode.")
    print("Press Enter to talk. Type 'switch' to change personality, 'quit' to exit.\n")

    while True:
        cmd = input("Press Enter to record: ").strip().lower()
        if cmd == "quit":
            break
        if cmd == "switch":
            personality = choose_personality()
            history = []
            continue

        audio = record_audio()
        user_text = transcribe(save_wav(audio))
        if not user_text:
            print("(Didn't catch anything - try again.)")
            continue
        print(f"You said: {user_text}")

        reply = get_reply(personality, history, user_text)
        print(f"Aurora ({personality}): {reply}")
        speak(personality, reply)


if __name__ == "__main__":
    main()