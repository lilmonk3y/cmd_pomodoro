#!/home/lilmonk3y/Scripts/temporizador_logger/temporizador_logguer/bin/python3

# active venv:  source temporizador_logguer/bin/activate ; deactivate

TIME_PERIOD = 61
PATH_PC = "~/Scripts/temporizador_logger/audio/JAAA.mp3"
PATH_VIDEO = "https://www.youtube.com/watch?v=SPXhPIfECIE"
POMODORO_TIME = 30
BETWEEN_POMODOROS_SOUND = "Scripts/temporizador_logger/audio/notification_sound_1.mp3"
PATH_TO_LOG = "Dropbox/obsidian_sync/obsidian_dropbox/logging/pomodoro_log.md"

import time
from datetime import datetime, timedelta
import os
import sys
from playsound import playsound

def print_pending_time(seconds):
    time_str = "{:02d}:{:02d}:{:02d}".format(seconds//3600, (seconds//60) % 60, seconds % 60)
    print("Faltan para terminar: {}".format(time_str) , end="\r")

def timer_audio():
    exit_code = os.system("open "+PATH_PC)
    if exit_code:
        os.system("google-chrome "+PATH_VIDEO)

def log(now, tag):
    text = pomo_log_line_entry(now, tag)
    with open(path_of_log_file(), "a") as log:
        log.write("\n" + text )
    play_sound()

def pomo_log_line_entry(now, tag):
    date = now.strftime("%y-%m-%d")
    time_str = now.strftime("%H:%M")
    text = "🍅 {} , {}".format(date, time_str)
    if tag:
        text = text + " , #{}".format(tag)
    return text 

def path_of_log_file():
    return path_to_file(PATH_TO_LOG)

def play_sound():
    path = path_to_file(BETWEEN_POMODOROS_SOUND)
    playsound(path)

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def must_log(seconds_since_last_pomodoro, pomodoro_duration_in_minutes):
    pomodoro_in_seconds = 60 * pomodoro_duration_in_minutes
    return seconds_since_last_pomodoro == pomodoro_in_seconds

##### main #####

minutes_count = TIME_PERIOD
if len(sys.argv) > 1:
    minutes_count = int(sys.argv[1])

tag = None
if len(sys.argv) > 2:
    tag = sys.argv[2]

seconds = minutes_count * 60

try:
    since_last_pomodoro = 0
    while 0 <= seconds:
        print_pending_time(seconds)
        if must_log(since_last_pomodoro, POMODORO_TIME):
            now = datetime.now()
            log(now, tag)
        time.sleep(1)
        seconds -= 1
        since_last_pomodoro += 1

    timer_audio()
    print("\nFelicitaciones por el período de estudio! Te mereces un descanso.")

except KeyboardInterrupt:
    print("\nRelog apagado")
