import subprocess
import time
import os
os.environ['PATH'] += os.pathsep + os.path.join(os.getcwd(), "test", "ovr_lipsync", "ffmpeg", "bin")
from pydub import AudioSegment
import json

def list_files(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            print(os.path.join(root, file))

class LipSyncGenerator:
    def __init__(self):
        self.viseme_em = [
          "sil", "PP", "FF", "TH", "DD",
          "kk", "CH", "SS", "nn", "RR",
          "aa", "E", "ih", "oh", "ou"]
        self.viseme = []
        self.exe_path = os.path.join(os.getcwd(), "test", "ovr_lipsync", "ovr_lipsync_exe", "ProcessWAV.exe")

    def convert_mp3_to_wav(self, mp3_filepath):
        audio = AudioSegment.from_mp3(mp3_filepath)
        # 使用 set_frame_rate 方法设置采样率
        audio = audio.set_frame_rate(44100)
        wav_filepath = mp3_filepath.rsplit(".", 1)[0] + ".wav"
        audio.export(wav_filepath, format="wav")
        return wav_filepath

    def run_exe_and_get_output(self, arguments):
        process = subprocess.Popen([self.exe_path] + arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                self.viseme.append(output.strip().decode())
        rc = process.poll()
        return rc

    def filter(self, viseme):
        new_viseme = []
        for v in self.viseme:
            if v in self.viseme_em:
                new_viseme.append(v)
        return new_viseme

    def generate_visemes(self, mp3_filepath):
        

        wav_filepath = self.convert_mp3_to_wav(mp3_filepath)
        arguments = ["--print-viseme-name", wav_filepath]
        self.run_exe_and_get_output(arguments)
        
        return self.filter(self.viseme)
        
    def consolidate_visemes(self, viseme_list):
        if not viseme_list:
            return []

        result = []
        current_viseme = viseme_list[0]
        count = 1

        for viseme in viseme_list[1:]:
            if viseme == current_viseme:
                count += 1
            else:
                result.append({"Lip": current_viseme, "Time": count*33})  # Multiply by 10 for duration in ms
                current_viseme = viseme
                count = 1

        # Add the last viseme to the result
        result.append({"Lip": current_viseme, "Time": count*33})  # Multiply by 10 for duration in ms

        new_data = []
        for i in range(len(result)):
            if result[i]['Time'] < 30:
                if len(new_data) > 0:
                    new_data[-1]['Time'] += result[i]['Time']
            else:
                new_data.append(result[i])
        return new_data
if __name__ == "__main__":
    start_time = time.time()
    lip_sync_generator = LipSyncGenerator()
    viseme_list = lip_sync_generator.generate_visemes("E:\\github\\Fay\\samples\\fay-man.mp3")
    print(viseme_list)
    consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
    print(json.dumps(consolidated_visemes))
    print(time.time() - start_time)
