import sys, piper, io, wave
import sounddevice as sd, numpy as np

voice = piper.PiperVoice.load('voices/en_US-ryan-high.onnx', config_path='voices/en_US-ryan-high.onnx.json')

text1 = "Shiver me timbers, glad to hear ye're feelin' good, matey!"
text2 = "What adventures be ye embarkin' on today?"

for i, text in enumerate([text1, text2]):
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        voice.synthesize_wav(text, wf)
    
    wav_buffer.seek(0)
    with wave.open(wav_buffer, 'rb') as wf:
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    
    audio_int16 = np.frombuffer(frames, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32) / 32767.0
    print(f'Chunk {i+1}: length = {len(audio_float)/rate:.2f} seconds')
    
    print(f"Playing chunk {i+1}...")
    sd.play(audio_float, samplerate=rate, blocking=True)
    print(f"Chunk {i+1} done playing.")
