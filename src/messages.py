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
    PomodoroBegin = auto()
    BreakBegin = auto()
    BreakFinished = auto()
    PomodoroInit = auto()
    PrinterReady = auto()
    AudioPomodoroFinished = auto()
    TimerInit = auto()
    TimerResumed = auto()
    TimerStopped = auto()
    TimerFinished = auto()
    AudioEnded = auto()
    ResumeTimer = auto()
    StopTimer = auto()
    AudioTerminate = auto()
    AddPurpose = auto()
    PurposeFinished = auto()
    PurposeAdded = auto()
    LayoutDraw = auto()
    StopStopwatch = auto()
    StopPrinter = auto()
    TagChange = auto()
    TagChanged = auto()
    TagFinished = auto()

@dataclass(frozen=True)
class EventMsg():
    kind : Event
    msg : str = ""

    def __str__(self):
        return "kind: {}, msg: {}".format(self.kind, self.msg)

class EventBrokerManager(BaseManager):
    pass

class EventBroker:
    def __init__(self):
        self._logger = logging.getLogger(".event_broker")

        self._msg_queue = queue.Queue()
        self._event_consumers = {event:[] for event in Event}
        self._msgs = []

    def suscribe(self, *events, suscriber):
        (ours, theirs) = Pipe()
        for event in events:
            if event in self._event_consumers.keys():
                self._logger.info("Process {} suscribed to event {}".format(getpid(),event))
                self._event_consumers[event].append((ours, suscriber))
            else:
                raise RuntimeError("Event {} is not a valid event".format(event))

        self._publish_previous_msgs(ours, suscriber, events)
        return theirs

    def publish(self, msg: EventMsg):
        self._msgs.append(msg)

        for consumer, consumer_id in self._event_consumers[msg.kind]:
            self._publish_msg_to_consumer(msg, consumer, consumer_id)

    def unsuscribe(self, suscriber_id, event_list):
        for event in event_list:
            for index, (_, theirs_id) in enumerate(self._event_consumers[event]):
                if theirs_id == suscriber_id:
                    self._event_consumers[event].pop(index)
                    self._logger.info("deleted consumer {} from event {}".format(suscriber_id, event))

    def _publish_previous_msgs(self, topic, consumer_id, events):
        for msg in filter(lambda msg: msg.kind in events, self._msgs):
            self._publish_msg_to_consumer(msg, topic, consumer_id)

    def _publish_msg_to_consumer(self, msg, consumer, consumer_id):
        consumer.send(msg)
        self._logger.info("Process {} has a new msg in it's pipe. msg: {}".format(consumer_id, msg))

def print_time(msg_queue, time):
    _send(msg_queue, EventMsg(Event.TimeChange, time))

def print_app_msg(msg_queue, msg):
    _send(msg_queue, EventMsg(Event.App, msg))

def print_cmd_msg(msg_queue, msg):
    _send(msg_queue, EventMsg(Event.Cmd, msg))

def event_terminate(msg_queue):
    _send(msg_queue, EventMsg(Event.Termination))

def event_playback(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioPlayback))

def event_audio_stopped(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioStopped))

def event_timer_init(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerInit))

def event_timer_stopped(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerStopped))

def event_timer_resumed(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerResumed))

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

def event_timer_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.TimerFinished))

def event_audio_ended(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioEnded))

def event_resume_timer(msg_queue):
    _send(msg_queue, EventMsg(Event.ResumeTimer))

def event_stop_timer(msg_queue):
    _send(msg_queue, EventMsg(Event.StopTimer))

def event_audio_terminate(msg_queue):
    _send(msg_queue, EventMsg(Event.AudioTerminate))

def event_add_purpose(msg_queue):
    _send(msg_queue, EventMsg(Event.AddPurpose))

def event_purpose_added(msg_queue, purpose):
    _send(msg_queue, EventMsg(Event.PurposeAdded, purpose))

def event_purpose_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.PurposeFinished))

def event_layout_draw(msg_queue):
    _send(msg_queue, EventMsg(Event.LayoutDraw))

def event_stop_stopwatch(msg_queue):
    _send(msg_queue, EventMsg(Event.StopStopwatch))

def event_stop_printer(msg_queue):
    _send(msg_queue, EventMsg(Event.StopPrinter))

def event_tag_change(msg_queue):
    _send(msg_queue, EventMsg(Event.TagChange))

def event_tag_changed(msg_queue, tag):
    _send(msg_queue, EventMsg(Event.TagChanged, tag))

def event_tag_finished(msg_queue):
    _send(msg_queue, EventMsg(Event.TagFinished))

def _send(msg_queue, msg: EventMsg):
    logger = logging.getLogger(".messages")
    logger.info("sending msg from {} {}".format(getpid(), msg))
    msg_queue.publish(msg)
