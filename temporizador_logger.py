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
import multiprocessing
import select
import signal
import math

##### timer #####

def timer(timer_pipe, sys_argv):
    """Timer process manages the pomodoros and the logging of them"""

    signal.signal(signal.SIGINT, timer_interrupted)

    minutes_count = TIME_PERIOD
    if len(sys_argv) > 1:
        minutes_count = int(sys_argv[1])

    tag = None
    if len(sys_argv) > 2:
        tag = sys_argv[2]

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
                timer_pipe.send("stoped")
                return
            else:
                raise RuntimeError(f"Message {msg} is unhandled by timer")

        if paused:
            continue

        print_pending_time(seconds)
        if pomodoro_ended(since_last_pomodoro, POMODORO_TIME):
            now = datetime.now()
            log(now, tag)
            timer_pipe.send("audio_pomodoro_finished")
            since_last_pomodoro = 0

        time.sleep(1)
        seconds -= 1
        since_last_pomodoro += 1

    timer_pipe.send("finished")

def timer_interrupted(signum, frame):
    print("\nRelog apagado")

def print_pending_time(seconds):
    time_str = "{:02d}:{:02d}:{:02d}".format(seconds//3600, (seconds//60) % 60, seconds % 60)
    print("Faltan para terminar: {}".format(time_str) , end="\r", flush=True)

def log(now, tag):
    text = pomo_log_line_entry(now, tag)
    with open(path_of_log_file(), "a") as log:
        log.write("\n" + text )

def pomo_log_line_entry(now, tag):
    date = now.strftime("%y-%m-%d")
    time_str = now.strftime("%H:%M")
    text = "🍅 {} , {}".format(date, time_str)
    if tag:
        text = text + " , #{}".format(tag)
    return text 

def path_of_log_file():
    return path_to_file(PATH_TO_LOG)

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def pomodoro_ended(seconds_since_last_pomodoro, pomodoro_duration_in_minutes):
    pomodoro_in_seconds = 60 * pomodoro_duration_in_minutes
    return seconds_since_last_pomodoro == pomodoro_in_seconds

##### stopwatch #####

def stopwatch_process():
    signal_handler = StopwatchSignalHandler()
    
    print("\nTemporizador iniciado")

    while signal_handler.KEEP_PROCESSING:
        time.sleep(1)
        signal_handler.SECONDS_COUNT += 1

    print("\nLa duración del temporizador fue de: {}".format(stopwach_msg(signal_handler.SECONDS_COUNT)))

def stopwach_msg(seconds):
    minutes = math.ceil(seconds/60)
    return f"{minutes} minutos" if minutes != 1 else f"{minutes} minuto"
    
class StopwatchSignalHandler:
    KEEP_PROCESSING = True
    SECONDS_COUNT = 0
    def __init__(self):
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.KEEP_PROCESSING = False

##### audio - play audio on background #####

def audio_process(audio_path):
    play_on_background(audio_path)

def play_on_background(audio_track_path):
    path = path_to_file(BETWEEN_POMODOROS_SOUND)
    playsound(path)

##### main - keyboard manager #####

def main():
    stopwatch = None

    main_pipe, timer_pipe = multiprocessing.Pipe()

    timer_process = multiprocessing.Process(target=timer, args=(timer_pipe, sys.argv))
    timer_process.start()

    while True:
        if main_pipe.poll():
            msg = main_pipe.recv()

            if msg == "finished":
                play_end_of_timer_audio()
                print("\nFelicitaciones por el período de estudio! Te mereces un descanso.")
                break

            elif msg == "stoped":
                print("\nRelog apagado")
                break

            elif msg == "audio_pomodoro_finished":
                play_audio_on_subprocess(BETWEEN_POMODOROS_SOUND)

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        try:
            key = get_key()
            match key:
                case "p":
                    print("\nCuenta atrás pausada.")
                    main_pipe.send("pause")

                case "c":
                    print("\nCuenta atrás reanudada.")
                    main_pipe.send("continue")

                case "f":
                    main_pipe.send("stop")
                
                case "t":
                    if stopwatch:
                        stopwatch.terminate()
                        stopwatch.join()
                        stopwatch = None
                    else:
                        stopwatch = multiprocessing.Process(target=stopwatch_process)
                        stopwatch.start()

                case "h":
                    print_manual()

        except KeyboardInterrupt:
            main_pipe.send("stop")
            break

    if stopwatch:
        stopwatch.terminate()

    timer_process.join()

def get_key():
    """Lee una tecla de manera no bloqueante."""
    if select.select([sys.stdin], [], [], 0.1)[0]:
        key = sys.stdin.read(1)
        return key

    return None

def play_end_of_timer_audio():
    exit_code = os.system("open "+PATH_PC)
    if exit_code:
        os.system("google-chrome "+PATH_VIDEO)

def play_audio_on_subprocess(audio_track_path):
    (multiprocessing.Process(target=audio_process, args=(audio_track_path,))).start()

def print_manual():
    manual = """
    Las opciones de teclas son:
    p   Pausar el temporizador
    c   Continuar con el temporizador
    f   Finalizar el temporizador
    t   Iniciar un stopwatch
    h   Mostrar esta guía de comandos
    """
    print(manual)

if __name__ == "__main__":
    main()
