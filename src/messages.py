from abc import abstractmethod, ABC
from enum import auto, Enum
from dataclasses import dataclass
import logging
import queue
from multiprocessing.managers import BaseManager
from multiprocessing import Pipe
from os import getpid

class Event(Enum):
    TimeChange = auto()
    App = auto()
    Cmd = auto()
    Termination = auto()
    AudioPlayback = auto()
    AudioStopped = auto()
    Stopped = auto()
    Resumed = auto()
    PomodoroBegin = auto()
    BreakBegin = auto()
    BreakFinished = auto()
    PomodoroInit = auto()
    TimerInit = auto()
    PrinterReady = auto()
    AudioPomodoroFinished = auto()
    TimerStopped = auto()
    TimerFinished = auto()
    AudioEnded = auto()
    StopTimer = auto()
    AudioTerminate = auto()

@dataclass(frozen=True)
class EventMsg():
    kind : Event
    msg : str = ""

    def __str__(self):
        return "kind: {}, msg: {}".format(self.kind, self.msg)

class Consumer(ABC):
    @abstractmethod
    def consume(self, event: Event):
        raise RuntimeError("Shouldn't be used")

class EventBrokerManager(BaseManager):
    pass

class EventBroker:
    def __init__(self):
        self._logger = logging.getLogger(".event_broker")

        self._msg_queue = queue.Queue()
        self._event_consumers = {event:[] for event in Event}

    def suscribe(self, *events):
        (ours, theirs) = Pipe()
        for event in events:
            if event in self._event_consumers.keys():
                self._logger.info("Process {} suscribed to event {}".format(getpid(),event))
                self._event_consumers[event].append(ours)
            else:
                raise RuntimeError("Event {} is not a valid event".format(event))

        return theirs

    def publish(self, msg: EventMsg):
        #assert self._event_consumers[msg.kind], "Tengo al menos un consumidor para el mensaje msg"

        for consumer in self._event_consumers[msg.kind]:
            consumer.send(msg)
            self._logger.info("Process {} has a new msg in it's pipe. msg: {}".format(getpid(), msg))

def print_time(msg_queue, time):
    _send(msg_queue, EventMsg(Event.TimeChange, time))

def print_app_msg(msg_queue, msg):
    _send(msg_queue, EventMsg(Event.App, msg))

def print_cmd_msg(msg_queue, msg):
    _send(msg_queue, EventMsg(Event.Cmd, msg))

def print_terminate(msg_queue):
    _send(msg_queue, EventMsg(Event.Termination))

def event_playback(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioPlayback))

def event_audio_stopped(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioStopped))

def event_stopped(msg_queue):
    _send(msg_queue, EventMsg(Event.Stopped))

def event_resumed(msg_queue):
    _send(msg_queue, EventMsg(Event.Resumed))

def event_timer_init(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerInit))

def event_pomodoro_init(msg_queue):
    _send(msg_queue, EventMsg(Event.PomodoroInit))

def event_pomodoro_begin(msg_queue):
    _send(msg_queue, EventMsg(Event.PomodoroBegin))

def event_break_begin(msg_queue):
    _send(msg_queue, EventMsg(Event.BreakBegin))

def event_break_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.BreakFinished))

def event_printer_ready(msg_queue):
    _send(msg_queue, EventMsg(Event.PrinterReady))

def event_audio_pomodoro_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioPomodoroFinished))

def event_timer_stopped(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerStopped))

def event_timer_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerFinished))

def event_audio_ended(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioEnded))

def event_stop_timer(msg_queue):
    _send(msg_queue, EventMsg(Event.StopTimer))

def event_audio_terminate(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioTerminate))

def _send(msg_queue, msg: EventMsg):
    logger = logging.getLogger(".messages")
    logger.info("sending msg from {} {}".format(getpid(), msg))
    msg_queue.publish(msg)
