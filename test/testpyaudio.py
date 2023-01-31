import pyaudio
audio = pyaudio.PyAudio()
print(audio.get_device_count())