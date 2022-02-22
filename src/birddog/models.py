import enum
from dataclasses import dataclass
import typing as tp

class OperationMode(enum.Enum):
    encode = enum.auto()
    decode = enum.auto()

class AudioOutput(enum.Enum):
    DecodeMain = enum.auto()
    DecodeComms = enum.auto()
    DecodeLoop = enum.auto()

class VideoOutput(enum.Enum):
    sdi = enum.auto()
    hdmi = enum.auto()
    LowLatency = enum.auto()
    NormalMode = enum.auto()

@dataclass
class AudioOutputSetup:
    input_gain: int
    output_gain: int
    output_select: AudioOutput

    @classmethod
    def from_api(cls, data: tp.Dict) -> 'AudioOutputSetup':
        kw = dict(
            input_gain=int(data['AnalogAudioInGain']),
            output_gain=int(data['AnalogAudioOutGain']),
            output_select=getattr(AudioOutput, data['AnalogAudiooutputselect']),
        )
        return cls(**kw)

@dataclass
class DeviceSettings:
    operation_mode: OperationMode
    video_output: VideoOutput
    audio_setup: AudioOutputSetup

    def to_form_data(self) -> tp.Dict:
        form_data = {
            'mode': self.operation_mode.name,
            'vid12g_loop_if': self.video_output.name,
            'AnalogAudioInGain': self.audio_setup.input_gain,
            'AnalogAudioOutGain': self.audio_setup.output_gain,
            'AnalogAudiooutputselect': self.audio_setup.output_select.name,
        }
        return form_data

@dataclass
class NdiSource:
    name: str
    address: tp.Optional[str] = None
    index: tp.Optional[int] = None
    is_current: tp.Optional[bool] = False

    def format(self):
        if self.is_current:
            prefix = '-->'
        else:
            prefix = '   '
        ix = self.index
        if ix is None:
            ix = '  '
        else:
            ix = f'{ix:2d}'
        return f'{prefix} [{ix}] "{self.name}" ({self.address})'
