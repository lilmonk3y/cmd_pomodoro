from abc import abstractmethod, ABC
from enum import StrEnum, auto
from dataclasses import dataclass
from multiprocessing import Queue

class MsgType(StrEnum):
    Time = auto()
    App = auto()
    Cmd = auto()
    Termination = auto()
    Event = auto()
    Empty = auto()

@dataclass(frozen=True)
class Msg():
    kind : MsgType
    msg : str

    def __str__(self):
        return "kind: {}, msg: {}".format(self.kind, self.msg)

class Event(StrEnum):
    AudioPlayback = auto()
    AudioStopped = auto()
    Stopped = auto()
    Resumed = auto()
    PomodoroBegin = auto()
    BreakBegin = auto()
    BreakFinished = auto()
    PomodoroInit = auto()
    TimerInit = auto()

class Consumer(ABC):
    @abstractmethod
    def consume(self, event: Event):
        raise RuntimeError("Shouldn't be used")

class EventBroker:
    def __init__(self):
        self._msg_queue = Queue()
        self._event_consumers = self._init_event_dict()

    def suscribe(self, consumer: Consumer, *events):
        for event in events:
            if event in self._event_consumers.keys():
                self._event_consumers[event].append(consumer)
            else:
                raise RuntimeError("Event {} is not a valid event".format(event))

    def publish(self, msg: Msg):
        assert msg.kind == MsgType.Event
        
        event = msg.msg
        for consumer in self._event_consumers[event]:
            consumer.consume(event)


    def _init_event_dict(self):
        event_consumers = dict()
        for event in Event:
            event_consumers[event] = []

        return event_consumers



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

def event_timer_init(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.TimerInit))

def event_pomodoro_init(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.PomodoroInit))

def event_pomodoro_begin(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.PomodoroBegin))

def event_break_begin(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.BreakBegin))

def event_break_finished(msg_queue):
    _send(msg_queue, Msg(MsgType.Event, Event.BreakFinished))

def _send(msg_queue, msg): # msg : Msg
    msg_queue.publish(msg)
