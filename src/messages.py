from enum import StrEnum, auto
from dataclasses import dataclass

@dataclass(frozen=True)
class Msg:
    kind : str# kind : MsgType
    msg : str

    def __str__(self):
        return "kind: {}, msg: {}".format(self.kind, self.msg)

class MsgType(StrEnum):
    Time = auto()
    App = auto()
    Cmd = auto()
    Termination = auto()
    Event = auto()
    Empty = auto()

class Event(StrEnum):
    AudioPlayback = auto()
    AudioStopped = auto()
    Stopped = auto()
    Resumed = auto()

def print_time(msg_queue, time):
    _send(msg_queue, Msg(MsgType.Time, time))

def print_app_msg(msg_queue, msg):
    _send(msg_queue, Msg(MsgType.App, msg))

def print_cmd_msg(msg_queue, msg):
    _send(msg_queue, Msg(MsgType.Cmd, msg))

def print_terminate(msg_queue):
    _send(msg_queue, Msg(MsgType.Termination, ""))

def event_playback(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.AudioPlayback))

def event_audio_stopped(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.AudioStopped))

def event_stopped(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.Stopped))

def event_resumed(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.Resumed))

def _send(msg_queue, msg): # msg : Msg
    msg_queue.put(msg)
