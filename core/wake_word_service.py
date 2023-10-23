import pvporcupine
from pvrecorder import PvRecorder
from utils import config_util as cfg

class PicoWakeWord:
    def __init__(self):
        self._porcupine = None
        self._recorder = None

    @property
    def porcupine(self):
        if not self._porcupine:
            self._porcupine = pvporcupine.create(
                access_key=cfg.picovoice_api_key,
                keyword_paths=["./ppn/hi-Fay-Fay_en_windows_v2_2_0.ppn"]
            )
        return self._porcupine

    @property
    def recorder(self):
        if not self._recorder:
            device_id = -1
            for i, device in enumerate(PvRecorder.get_available_devices()):
                if device.find(cfg.config['source']['record']['device']) >= 0:
                    device_id = i
            self._recorder = PvRecorder(device_index=device_id, frame_length=self.porcupine.frame_length)
        return self._recorder

    def start(self):
        if not self._recorder:
            self.recorder.start()

    def detect_wake_word(self):
        if not self._recorder:
            self.start()
        pcm = self.recorder.read()
        result = self.porcupine.process(pcm)
        if result >= 0:
            self.delete()
            return True
        return False

    def delete(self):
        if hasattr(self._porcupine, "delete"):
            self._porcupine.delete()
            self._porcupine = None
        if hasattr(self._recorder, "delete"):
            self._recorder.delete()
            self._recorder = None