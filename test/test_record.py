import wave
import numpy as np
import pyaudio

def save_audio_to_wav(data, sample_rate, filename):
    # 确保数据类型为 int16
    if data.dtype != np.int16:
        data = data.astype(np.int16)
    
    # 打开 WAV 文件
    with wave.open(filename, 'wb') as wf:
        # 设置音频参数
        n_channels = 1  # 单声道
        sampwidth = 2   # 16 位音频，每个采样点 2 字节
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

def process_audio_data(audio_data_list, channels):
    # 将累积的音频数据块连接起来
    data = b''.join(audio_data_list)
    # 将字节数据转换为 numpy 数组
    data = np.frombuffer(data, dtype=np.int16)
    # 重塑数组，将数据分离成多个声道
    data = np.reshape(data, (-1, channels))
    # 对所有声道的数据进行平均，生成单声道
    mono_data = np.mean(data, axis=1).astype(np.int16)
    return mono_data

# 示例使用
def main():
    # 音频参数
    sample_rate = 44100  # 采样率
    channels = 1         # 声道数（根据您的实际情况）
    chunk_size = 1024    # 每次读取的帧数
    record_seconds = 5   # 录音时长
    output_filename = 'output.wav'  # 输出文件名

    # 初始化 PyAudio
    p = pyaudio.PyAudio()
    device_info = p.get_device_info_by_index(0)
    # channels = device_info.get('maxInputChannels', 1)
    print(channels)
    sample_rate = int(device_info.get('defaultSampleRate', 44100))
    stream = p.open(format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=chunk_size)

    print("开始录音...")

    audio_data_list = []

    # 录音循环
    for _ in range(int(sample_rate / chunk_size * record_seconds)):
        data = stream.read(chunk_size)
        data = np.frombuffer(data, dtype=np.int16)
        # 重塑数组，将数据分离成多个声道
        data = np.reshape(data, (-1, channels))
        # 对所有声道的数据进行平均，生成单声道
        mono = np.mean(data, axis=1).astype(np.int16)
        # 转换回字节格式
        data = mono.tobytes()
        audio_data_list.append(data)

    print("录音结束。")

    # 停止并关闭流
    stream.stop_stream()
    stream.close()
    p.terminate()

    # 处理音频数据
    mono_data = process_audio_data(audio_data_list, channels)

    # 保存为 WAV 文件
    save_audio_to_wav(mono_data, sample_rate, output_filename)

    print(f"音频已保存为 {output_filename}")

if __name__ == '__main__':
    main()
