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

def print_pending_time(end):
    td = end - datetime.now()
    time_str = "{:02d}:{:02d}:{:02d}".format(td.seconds//3600, (td.seconds//60) % 60, td.seconds % 60)
    print("Faltan para terminar: {}".format(time_str) , end="\r")

def timer_audio():
    exit_code = os.system("open "+PATH_PC)
    if exit_code:
        os.system("google-chrome "+PATH_VIDEO)

def log_if_apply(now, tss, tags):
    if tss and (tss[0] < now):
        ts = tss.pop(0)
        text = pomo_log_line_entry(ts, now, tags)
        with open(path_of_log_file(), "a") as log:
            log.write("\n" + text )
        play_sound()

def play_sound():
    path = path_to_file(BETWEEN_POMODOROS_SOUND)
    playsound(path)

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def path_of_log_file():
    return path_to_file(PATH_TO_LOG)

def pomo_log_line_entry(ts, today, tags):
    date = today.strftime("%y-%m-%d")
    time_str = ts.strftime("%H:%M")
    text = "🍅 {} , {}".format( date, time_str)
    if tags:
        text = text + " , #{}".format(tags[0])
    return text 

def list_of_timestamps(minutes_of_timer):
    return [datetime.now() + timedelta(minutes=POMODORO_TIME*i) for i in range(1, minutes_of_timer//POMODORO_TIME + 1)]

##### main #####

minutes_count = TIME_PERIOD
if len(sys.argv) > 1:
    minutes_count = int(sys.argv[1])

tags = []
if len(sys.argv) > 2:
    tags.append(sys.argv[2])

begin_time = datetime.now()
end_time = begin_time + timedelta(minutes=minutes_count ,seconds=1)
log_timestamps = list_of_timestamps(minutes_count)

try:
    while datetime.now() < end_time:
        print_pending_time(end_time)
        log_if_apply(datetime.now(), log_timestamps, tags)
        time.sleep(1)

    timer_audio()
    print("\nFelicitaciones por el período de estudio! Te mereces un descanso.")

except KeyboardInterrupt:
    print("\nRelog apagado")

