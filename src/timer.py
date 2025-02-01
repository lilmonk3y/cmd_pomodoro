from datetime import datetime
import time
from os import getpid

from messages import *
from utils import path_to_file

def timer(minutes_count, tag, log_file, pomodoro_time, msg_queue, purpose):
    """Timer process manages the pomodoros and the logging of them"""
    
    (Timer(minutes_count=minutes_count,
           msg_queue=msg_queue,
           pomodoro_time=pomodoro_time,
           log_file=log_file,
           tag=tag,
           purpose=purpose)).run()

def pomodoro(pomodoros, tag, pomodoro_time, pomodoro_break_duration, path_to_log, msg_queue, purpose):
    (Pomodoro(pomodoros=pomodoros,
           msg_queue=msg_queue,
           pomodoro_time=pomodoro_time,
           log_file=path_to_log,
           tag=tag,
           pomodoro_break_duration=pomodoro_break_duration,
           purpose=purpose)).run()

class Pomodoro:
    def __init__(self, 
                 pomodoros,
                 msg_queue, 
                 pomodoro_time,
                 log_file,
                 tag,
                 pomodoro_break_duration,
                 purpose):
        self._msg_queue=msg_queue
        self._pipe = msg_queue.suscribe(*[event for event in Event], suscriber=getpid())
        self._pomodoro_time=pomodoro_time
        self._log_file=log_file
        self._tag=tag
        self._pomodoros=pomodoros
        self._pomodoro_break_duration=pomodoro_break_duration
        self._purpose = purpose
        self._seconds = self._pomodoro_time * 60

        self._wait_printer = True
        self._must_exit = False
        self._on_break = False

    def run(self):
        while self._wait_printer:
            self._poll_pipe()

        self._set_pomodoro()

        while 0 != self._pomodoros: 
            self._poll_pipe()

            if self._must_exit:
                break

            self._print_seconds_to_screen()
            
            if self._is_pomodoro_ended():
                now = datetime.now()
                self._log_to_file(now)
                self._print_pomodoro_finished(now)

                self._pomodoros -= 1

                if self._pomodoros != 0: 
                    self._set_break()

            elif self._is_break_ended():
                event_break_finished(self._msg_queue)
                self._set_pomodoro()

            time.sleep(1)
            self._seconds -= 1

        self._msg_queue.unsuscribe(getpid(), [event for event in Event])
        event_timer_finished(self._msg_queue)
    
    def _set_pomodoro(self):
        self._on_break = False
        self._seconds = self._pomodoro_time * 60
        event_pomodoro_begin(self._msg_queue)
        
    def _set_break(self):
        self._on_break = True
        self._seconds = self._pomodoro_break_duration * 60
        event_audio_pomodoro_finished(self._msg_queue)
        event_break_begin(self._msg_queue)

    def _poll_pipe(self):
        while self._pipe.poll():
            msg = self._pipe.recv()
            match msg.kind:
                case Event.PrinterReady:
                    self._wait_printer = False

                case Event.StopTimer:
                    self._paused = True
                    event_timer_stopped(self._msg_queue)
                    print_app_msg(self._msg_queue,"Cuenta atrás pausada.")

                case Event.ResumeTimer:
                    self._paused = False
                    event_timer_resumed(self._msg_queue)
                    print_app_msg(self._msg_queue,"Cuenta atrás reanudada.")

                case Event.Termination:
                    self._must_exit = True

                case Event.PurposeAdded:
                    self._purpose = msg.msg

    def _print_seconds_to_screen(self):
        print_time(self._msg_queue, self._print_pending_time_msg())

    def _print_pending_time_msg(self):
        s=self._seconds
        return "{:02d}:{:02d}:{:02d}".format(s//3600, (s//60) % 60, s % 60)

    def _is_pomodoro_ended(self):
        return not self._on_break and self._seconds == 0

    def _is_break_ended(self):
        return self._on_break and self._seconds == 0

    def _log_to_file(self, now):
        text = pomo_log_line_entry(now, self._tag, self._purpose)
        with open(path_to_file(self._log_file), "a") as log:
            log.write("\n" + text )
            
    def _print_pomodoro_finished(self, now):
        text = pomo_log_line_entry(now, self._tag, self._purpose)
        print_app_msg(self._msg_queue,text)

class Timer:
    def __init__(self, 
                 minutes_count, 
                 msg_queue, 
                 pomodoro_time,
                 log_file,
                 tag,
                 purpose):
        self._seconds=minutes_count*60
        self._msg_queue=msg_queue
        self._pipe = self._msg_queue.suscribe(*[event for event in Event], suscriber=getpid())
        self._pomodoro_time=pomodoro_time
        self._log_file=log_file
        self._tag=tag
        self._purpose = purpose

        self._wait_printer = True
        self._since_last_pomodoro = 0
        self._paused = False
        self._must_exit = False

    def run(self):
        while self._wait_printer:
            self._poll_pipe()

        while 0 <= self._seconds: 
            self._poll_pipe()

            if self._paused:
                continue

            if self._must_exit:
                return

            self._print_seconds_to_screen()
            
            if self._is_pomodoro_ended():
                now = datetime.now()
                self._log_to_file(now)
                self._print_pomodoro_finished(now)

                if 0 < self._seconds:
                    event_audio_pomodoro_finished(self._msg_queue)

                self._since_last_pomodoro = 0

            time.sleep(1)
            self._seconds -= 1
            self._since_last_pomodoro += 1

        self._msg_queue.unsuscribe(getpid(), [event for event in Event])
        event_timer_finished(self._msg_queue)

    def _poll_pipe(self):
        while self._pipe.poll():
            msg = self._pipe.recv()
            
            match msg.kind:
                case Event.PrinterReady:
                    self._wait_printer = False

                case Event.StopTimer:
                    self._paused = True
                    event_timer_stopped(self._msg_queue)
                    print_app_msg(self._msg_queue,"Cuenta atrás pausada.")

                case Event.ResumeTimer:
                    self._paused = False
                    event_timer_resumed(self._msg_queue)
                    print_app_msg(self._msg_queue,"Cuenta atrás reanudada.")

                case Event.Termination:
                    self._must_exit = True

                case Event.PurposeAdded:
                    self._purpose = msg.msg

    def _print_seconds_to_screen(self):
        print_time(self._msg_queue, self._print_pending_time_msg())

    def _print_pending_time_msg(self):
        s=self._seconds
        return "{:02d}:{:02d}:{:02d}".format(s//3600, (s//60) % 60, s % 60)

    def _is_pomodoro_ended(self):
        pomodoro_in_seconds = 60 * self._pomodoro_time
        return pomodoro_in_seconds <= self._since_last_pomodoro

    def _log_to_file(self, now):
        text = pomo_log_line_entry(now, self._tag, self._purpose)
        with open(path_to_file(self._log_file), "a") as log:
            log.write("\n" + text )
            
    def _print_pomodoro_finished(self, now):
        print_app_msg(self._msg_queue,pomo_log_line_entry(now,self._tag, self._purpose))

def pomo_log_line_entry(now, tag, purpose=None):
    date = now.strftime("%y-%m-%d")
    time_str = now.strftime("%H:%M")
    text = "🍅 {} , {}".format(date, time_str)
    if tag:
        text += " , #{}".format(tag)
    if purpose:
        if tag:
            text += " , {}".format(purpose)
        else:
            text += " , , {}".format(purpose)

    return text
