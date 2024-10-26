from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

sessions = AudioUtilities.GetAllSessions()
for session in sessions:
    volume = session._ctl.QueryInterface(IAudioEndpointVolume)
    if session.Process and session.Process.name() == "vscode.exe":
        if session.SimpleAudioVolume.GetMasterVolume() > 0:
            print("音频正在播放")
        else:
            print("音频已停止")
