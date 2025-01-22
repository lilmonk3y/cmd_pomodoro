from datetime import datetime
import time

from messages import print_time, print_app_msg, event_pomodoro_begin, event_break_begin, event_break_finished
from utils import path_to_file

def timer(timer_pipe, minutes_count, tag, log_file, pomodoro_time, msg_queue):
    """Timer process manages the pomodoros and the logging of them"""
    
    (Timer(minutes_count=minutes_count,
           pipe=timer_pipe,
           msg_queue=msg_queue,
           pomodoro_time=pomodoro_time,
           log_file=log_file,
           tag=tag)).run()

def pomodoro(pipe, pomodoros, tag, pomodoro_time, pomodoro_break_duration, path_to_log, msg_queue):
    (Pomodoro(pomodoros=pomodoros,
           pipe=pipe,
           msg_queue=msg_queue,
           pomodoro_time=pomodoro_time,
           log_file=path_to_log,
           tag=tag,
           pomodoro_break_duration=pomodoro_break_duration)).run()

class Pomodoro:
    def __init__(self, 
                 pomodoros,
                 pipe, 
                 msg_queue, 
                 pomodoro_time,
                 log_file,
                 tag,
                 pomodoro_break_duration):
        self._pipe=pipe
        self._msg_queue=msg_queue
        self._pomodoro_time=pomodoro_time
        self._log_file=log_file
        self._tag=tag
        self._pomodoros=pomodoros
        self._pomodoro_break_duration=pomodoro_break_duration

        self._must_exit = False
        self._on_break = False
        self._seconds = None

    def run(self):
        self._set_pomodoro()

        while 0 != self._pomodoros: 
            self._poll_pipe()

            if self._must_exit:
                return

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
                self._pipe.send("audio_break_ended")
                self._set_pomodoro()

            time.sleep(1)
            self._seconds -= 1

        self._pipe.send("finished")

    def _set_pomodoro(self):
        self._on_break = False
        self._seconds = self._pomodoro_time * 60
        event_pomodoro_begin(self._msg_queue)
        
    def _set_break(self):
        self._on_break = True
        self._seconds = self._pomodoro_break_duration * 60
        self._pipe.send("audio_pomodoro_finished")
        event_break_begin(self._msg_queue)

    def _poll_pipe(self):
        if self._pipe.poll():
            msg = self._pipe.recv()

            if msg == "pause":
                self._paused = True
            elif msg == "continue":
                self._paused = False
            elif msg == "stop":
                self._pipe.send("stopped")
                self._must_exit = True
            else:
                raise RuntimeError(f"Message {msg} is unhandled by timer")

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
        text = pomo_log_line_entry(now, self._tag)
        with open(path_to_file(self._log_file), "a") as log:
            log.write("\n" + text )
            
    def _print_pomodoro_finished(self, now):
        print_app_msg(self._msg_queue,pomo_log_line_entry(now,self._tag))
class Timer:
    def __init__(self, 
                 minutes_count, 
                 pipe, 
                 msg_queue, 
                 pomodoro_time,
                 log_file,
                 tag):
        self._seconds=minutes_count*60
        self._pipe=pipe
        self._msg_queue=msg_queue
        self._pomodoro_time=pomodoro_time
        self._log_file=log_file
        self._tag=tag

        self._since_last_pomodoro = 0
        self._paused = False
        self._must_exit = False

    def run(self):
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
                    self._pipe.send("audio_pomodoro_finished")

                self._since_last_pomodoro = 0

            time.sleep(1)
            self._seconds -= 1
            self._since_last_pomodoro += 1

        self._pipe.send("finished")

    def _poll_pipe(self):
        if self._pipe.poll():
            msg = self._pipe.recv()

            if msg == "pause":
                self._paused = True
            elif msg == "continue":
                self._paused = False
            elif msg == "stop":
                self._pipe.send("stopped")
                self._must_exit = True
            else:
                raise RuntimeError(f"Message {msg} is unhandled by timer")

    def _print_seconds_to_screen(self):
        print_time(self._msg_queue, self._print_pending_time_msg())

    def _print_pending_time_msg(self):
        s=self._seconds
        return "{:02d}:{:02d}:{:02d}".format(s//3600, (s//60) % 60, s % 60)

    def _is_pomodoro_ended(self):
        pomodoro_in_seconds = 60 * self._pomodoro_time
        return pomodoro_in_seconds <= self._since_last_pomodoro

    def _log_to_file(self, now):
        text = pomo_log_line_entry(now, self._tag)
        with open(path_to_file(self._log_file), "a") as log:
            log.write("\n" + text )
            
    def _print_pomodoro_finished(self, now):
        print_app_msg(self._msg_queue,pomo_log_line_entry(now,self._tag))

def pomo_log_line_entry(now, tag):
    date = now.strftime("%y-%m-%d")
    time_str = now.strftime("%H:%M")
    text = "🍅 {} , {}".format(date, time_str)
    if tag:
        text = text + " , #{}".format(tag)
    return text
