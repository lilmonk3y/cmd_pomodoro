from datetime import datetime
import time

from messages import print_time, print_app_msg
from utils import path_to_file

def timer(timer_pipe, minutes_count, tag, log_file, pomodoro_time, msg_queue):
    """Timer process manages the pomodoros and the logging of them"""

    seconds = minutes_count * 60
    since_last_pomodoro = 0
    paused = False

    while 0 <= seconds:
        if timer_pipe.poll():
            msg = timer_pipe.recv()

            if msg == "pause":
                paused = True
            elif msg == "continue":
                paused = False
            elif msg == "stop":
                timer_pipe.send("stopped")
                return
            else:
                raise RuntimeError(f"Message {msg} is unhandled by timer")

        if paused:
            continue

        print_time(msg_queue, print_pending_time_msg(seconds))

        if pomodoro_ended(since_last_pomodoro, pomodoro_time):
            now = datetime.now()
            log(now, tag, log_file)
            print_app_msg(msg_queue,pomo_log_line_entry(now,tag))
            if 0 < seconds:
                timer_pipe.send("audio_pomodoro_finished")
            since_last_pomodoro = 0

        time.sleep(1)
        seconds -= 1
        since_last_pomodoro += 1

    timer_pipe.send("finished")

def print_pending_time_msg(seconds):
    return "{:02d}:{:02d}:{:02d}".format(seconds//3600, (seconds//60) % 60, seconds % 60)

def log(now, tag, log_file):
    text = pomo_log_line_entry(now, tag)
    with open(path_to_file(log_file), "a") as log:
        log.write("\n" + text )

def pomo_log_line_entry(now, tag):
    date = now.strftime("%y-%m-%d")
    time_str = now.strftime("%H:%M")
    text = "🍅 {} , {}".format(date, time_str)
    if tag:
        text = text + " , #{}".format(tag)
    return text 

def pomodoro_ended(seconds_since_last_pomodoro, pomodoro_duration_in_minutes):
    pomodoro_in_seconds = 60 * pomodoro_duration_in_minutes
    return seconds_since_last_pomodoro == pomodoro_in_seconds
