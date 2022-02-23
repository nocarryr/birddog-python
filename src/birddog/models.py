import enum
from dataclasses import dataclass
import typing as tp

class OperationMode(enum.Enum):
    """Operation Mode
    """
    encode = enum.auto()        #: Encode to NDI
    decode = enum.auto()        #: Decode from NDI

class AudioOutput(enum.Enum):
    """Source for the analog audio output
    """
    DecodeMain = enum.auto()    #: Main NDI audio stream
    DecodeComms = enum.auto()   #: Comms (intercom over NDI)
    DecodeLoop = enum.auto()    #: Loop out from the video (SDI or HDMI) input

class VideoOutput(enum.Enum):
    """Video output selection
    """
    sdi = enum.auto()           #: Output SDI
    hdmi = enum.auto()          #: Output HDMI
    LowLatency = enum.auto()    #: (documentation is unclear)
    NormalMode = enum.auto()    #: (documentation is unclear)

@dataclass
class AudioOutputSetup:
    """Configuration for the analog audio output
    """
    input_gain: int             #: Input gain in the range of 0 to 100
    output_gain: int            #: Output gain in the range of 0 to 100
    output_select: AudioOutput  #: The source for the analog output

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
    """Device settings
    """
    operation_mode: OperationMode   #: Operation mode
    video_output: VideoOutput       #: Video output selection
    audio_setup: AudioOutputSetup   #: Audio output configuration

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
    """An NDI source detected by the device
    """
    name: str                               #: The source name
    address: tp.Optional[str] = None        #: The source's IP address
    index: tp.Optional[int] = None          #: Index of the source in the list
    is_current: tp.Optional[bool] = False   #: Whether the source is currently selected

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
