#!/home/lilmonk3y/Scripts/temporizador_logger/temporizador_logguer/bin/python3

# active venv:  source temporizador_logguer/bin/activate ; deactivate

import time
from datetime import datetime, timedelta
import os
import sys
import multiprocessing
import select
import signal
import math
import pydub
import simpleaudio
from configparser import ConfigParser
import dataclasses as dc


##### timer #####

def timer(timer_pipe, minutes_count, tag, log_file, pomodoro_time):
    """Timer process manages the pomodoros and the logging of them"""

    signal.signal(signal.SIGINT, timer_interrupted)

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
        if pomodoro_ended(since_last_pomodoro, pomodoro_time):
            now = datetime.now()
            log(now, tag, log_file)
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

def audio_process(audio_path, audio_pipe):
    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = "timer_audio.wav"

    try:
        audio.export(NEW_AUDIO_PATH, format="wav")
        wave_object = simpleaudio.WaveObject.from_wave_file(NEW_AUDIO_PATH)
        play_object = wave_object.play()
        while play_object.is_playing():
            if audio_pipe.poll():
                msg = audio_pipe.recv()

                if msg == "audio_terminate":
                    play_object.stop()
                    break
                else:
                    time.sleep(0.5)

        audio_pipe.send("audio_ended")
        audio_pipe.close()

    finally:
        if os.path.exists(NEW_AUDIO_PATH):
            os.remove(NEW_AUDIO_PATH)

##### main - keyboard manager #####

def main():
    config = load_config_from_file()
    args = read_input(sys.argv, config)

    stopwatch = None

    main_pipe, timer_pipe = multiprocessing.Pipe()
    timer_process = multiprocessing.Process(target=timer, args=(timer_pipe, args.minutes_count, args.tag, config.path_to_log, config.pomodoro_time))
    timer_process.start()

    audio_pipe_father, audio_pipe_child = multiprocessing.Pipe()
    audio_process = None

    while True:
        if main_pipe.poll():
            msg = main_pipe.recv()

            if msg == "finished":
                audio_process = play_audio_on_subprocess(config.path_pc, audio_pipe_child)

            elif msg == "stoped":
                print("\nRelog apagado")
                break

            elif msg == "audio_pomodoro_finished":
                play_audio_on_subprocess(config.between_pomodoros_sound, audio_pipe_child)

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        if audio_process and audio_pipe_father.poll():
            msg = audio_pipe_father.recv()

            if msg == "audio_ended":
                print("\nFelicitaciones por el período de estudio! Te mereces un descanso.")
                break

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
                
                case "s":
                    if audio_process:
                        audio_pipe_father.send("audio_terminate")
                        audio_process.join()

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

def play_audio_on_subprocess(audio_track_path, audio_pipe):
    process = multiprocessing.Process(target=audio_process, args=(audio_track_path, audio_pipe))
    process.start()
    return process

def print_manual():
    manual = """
    Las opciones de teclas son:
    p   Pausar el temporizador
    c   Continuar con el temporizador
    f   Finalizar el temporizador
    t   Iniciar un stopwatch
    s   Detener la reproducción del sonido de finalización del timer
    h   Mostrar esta guía de comandos
    """
    print(manual)

def load_config_from_file(file="config.ini", env="PRODUCTION"):
    if not os.path.exists(file):
        raise RuntimeError("The config file {} doesn't exists".format(file))
    
    config = ConfigParser()
    config.read(file)
    if not config[env]:
        raise RuntimeError("The config file {} doesn't have the expected environment {}.".format(file, env))

    return build_config_file(config[env])

def build_config_file(config_map):
    fields = dc.fields(Config)
    field_keys = list(map(lambda f: f.name, fields))
    keys = list(config_map.keys())
    if not set(keys).issubset(field_keys):
        raise RuntimeError("There are missing keys in the config file. Expected keys: {}. Actual keys: {}".format(field_keys, keys))

    return Config(
            time_period= int(config_map["time_period"]),
            pomodoro_time= int(config_map["pomodoro_time"]),
            path_pc= config_map["path_pc"],
            between_pomodoros_sound= config_map["between_pomodoros_sound"],
            path_to_log= config_map["path_to_log"]
            )

@dc.dataclass(frozen=True)
class Config:
    time_period : int
    pomodoro_time : int
    path_pc : str
    between_pomodoros_sound : str
    path_to_log : str

def read_input(argv, config):
    minutes_count = config.time_period
    if len(argv) > 1:
        minutes_count = int(argv[1])

    tag = None
    if len(argv) > 2:
        tag = argv[2]

    return Input(
            minutes_count=minutes_count,
            tag=tag)

@dc.dataclass(frozen=True)
class Input:
    minutes_count : int
    tag : str

def write_config(file="config.ini", env="TEST"):
    config_object = ConfigParser()

    # Add server configuration to the config object
    config_object[env] = {
    "TIME_PERIOD": 2,
    "POMODORO_TIME": 1,
    "PATH_PC": "Scripts/temporizador_logger/audio/JAAA.mp3",
    "BETWEEN_POMODOROS_SOUND": "Scripts/temporizador_logger/audio/notification_sound_1.mp3",
    "PATH_TO_LOG": "Scripts/temporizador_logger/test/pomodoro_log.md"
    }

    with open('config.ini', 'a') as conf: 
        config_object.write(conf)

if __name__ == "__main__":
    main()
