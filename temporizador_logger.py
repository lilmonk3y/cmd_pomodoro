#!/home/lilmonk3y/Scripts/temporizador_logger/temporizador_logguer/bin/python3

# active venv:  source temporizador_logguer/bin/activate ; deactivate

import time
from datetime import datetime, timedelta
import os
import sys
import multiprocessing
import subprocess
import select
import signal
import math
import pydub
import simpleaudio
from configparser import ConfigParser
import dataclasses as dc
import argparse
import wave
import curses
from enum import StrEnum, auto

##### timer #####

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
                timer_pipe.send("stoped") # TODO fix typo
                return
            else:
                raise RuntimeError(f"Message {msg} is unhandled by timer")

        if paused:
            continue

        print_time(msg_queue, print_pending_time_msg(seconds))

        if pomodoro_ended(since_last_pomodoro, pomodoro_time):
            now = datetime.now()
            log(now, tag, log_file)
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

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def pomodoro_ended(seconds_since_last_pomodoro, pomodoro_duration_in_minutes):
    pomodoro_in_seconds = 60 * pomodoro_duration_in_minutes
    return seconds_since_last_pomodoro == pomodoro_in_seconds

##### stopwatch #####

def stopwatch_process(msg_queue):
    signal_handler = StopwatchSignalHandler()
    
    print_cmd_msg(msg_queue,"Temporizador iniciado")

    while signal_handler.KEEP_PROCESSING:
        time.sleep(1)
        signal_handler.SECONDS_COUNT += 1

    print_cmd_msg(msg_queue,"Temporizador duro: {}".format(stopwach_msg(signal_handler.SECONDS_COUNT)))

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

        continue_play = when_to_stop(NEW_AUDIO_PATH)
        # and play_object.is_playing()
        while continue_play() :
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

def when_to_stop(wav_file):
    length = length_in_seconds(wav_file)
    end_of_song = datetime.now() + timedelta(seconds=(length-1))
    return lambda: datetime.now() < end_of_song

def length_in_seconds(file):
    length = None
    with wave.open(file, 'rb') as wav:
        length = wav.getnframes() / float(wav.getframerate())
    return int(length)

def audio_process_short(audio_path):
    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = "pomo_audio.wav"

    try:
        audio.export(NEW_AUDIO_PATH, format="wav")
        wave_object = simpleaudio.WaveObject.from_wave_file(NEW_AUDIO_PATH)
        play_object = wave_object.play()
        time.sleep(length_in_seconds(NEW_AUDIO_PATH))

    finally:
        if os.path.exists(NEW_AUDIO_PATH):
            os.remove(NEW_AUDIO_PATH)

##### printer - outputs to console in one place #####

def print_time(msg_queue, time):
    _print(msg_queue, Msg(MsgType.Time, time))

def print_cmd_msg(msg_queue, msg):
    _print(msg_queue, Msg(MsgType.Cmd, msg))

def print_app_msg(msg_queue, msg):
    _print(msg_queue, Msg(MsgType.App, msg))

def print_terminate(msg_queue):
    _print(msg_queue, Msg(MsgType.Termination, ""))

def _print(msg_queue, msg): # msg : Msg
    msg_queue.put(msg)

def printer(msg_queue):
    last_msg = {"time":"","cmd":"","app":""}
    lines = []

    while True:
        while not msg_queue.empty():
            msg = msg_queue.get()

            if msg.kind == MsgType.Termination:
                print("Bye", end="\r", flush=True)
                return
            
            lines.append(msg)

        line = Msg(MsgType.Empty,"") if not lines else lines.pop()

        str_msg, last_msg = printer_msg(line,last_msg)
        print(str_msg,
              end="\r",
              flush=True)
              
        time.sleep(0.1)

def printer_msg(msg, last_msg):
    line = last_msg
    match msg.kind:
        case MsgType.Time:
            line["time"] = msg.msg

        case MsgType.Cmd:
            line["cmd"] = msg.msg

        case MsgType.App:
            line["app"] = msg.msg

        case MsgType.Empty:
            pass

        case _:
            raise RuntimeError("msg {} unhandled".format(msg))

    return "Time: {time:8} - cmd msgs: {cmd:20} - app msgs: {app:20}".format(**line), line

#def printer(msg_queue):
#    curses.wrapper(printer_display, msg_queue)

def printer_display(stdscr, msg_queue):
    curses.curs_set(0)
    stdscr.clear()
    stdscr.refresh()

    lines = []

    while True:
        while not msg_queue.empty():
            msg = msg_queue.get()

            if msg.type == MsgType.Termination:
                curses.endwin()
                return
            
            lines.append(msg)

        line = "" if not lines else lines.pop()

        stdscr.clear()
        stdscr.addstr(1,0,line)
        stdscr.refresh()

        time.sleep(0.1)

@dc.dataclass
class Msg:
    kind : str# kind : MsgType
    msg : str

class MsgType(StrEnum):
    Time = auto()
    Cmd = auto()
    App = auto()
    Termination = auto()
    Empty = auto()

##### main - keyboard manager #####

def main():
    args = read_input()
    config = load_config_from_file(args=args)

    msg_queue = multiprocessing.Queue()
    printer_process = multiprocessing.Process(target=printer, args=(msg_queue,))
    printer_process.start()

    stopwatch = None

    main_pipe, timer_pipe = multiprocessing.Pipe()
    timer_process = multiprocessing.Process(target=timer, args=(timer_pipe, args.minutes_count, args.tag, config.path_to_log, config.pomodoro_time, msg_queue))
    timer_process.start()

    audio_pipe_father, audio_pipe_child = multiprocessing.Pipe()
    audio_process = None

    while True:
        if main_pipe.poll():
            msg = main_pipe.recv()

            if msg == "finished":
                publish_notification(finished_info_msg(args))
                audio_process = play_audio_on_subprocess(config.path_pc, audio_pipe_child)

            elif msg == "stoped":
                print_app_msg(msg_queue, "Relog apagado")
                break

            elif msg == "audio_pomodoro_finished":
                 (multiprocessing.Process(target=audio_process_short, args=(config.between_pomodoros_sound,))).start()

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        if audio_process and audio_pipe_father.poll():
            msg = audio_pipe_father.recv()

            if msg == "audio_ended":
                print_app_msg(msg_queue, "Felicitaciones por el período de estudio! Te mereces un descanso.")
                break

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        try:
            key = get_key()
            match key:
                case "p":
                    print_cmd_msg(msg_queue,"Cuenta atrás pausada.")
                    main_pipe.send("pause")

                case "c":
                    print_cmd_msg(msg_queue,"Cuenta atrás reanudada.")
                    main_pipe.send("continue")

                case "f":
                    main_pipe.send("stop")
                
                case "t":
                    if stopwatch:
                        stopwatch.terminate()
                        stopwatch.join()
                        stopwatch = None
                    else:
                        stopwatch = multiprocessing.Process(target=stopwatch_process, args=(msg_queue,))
                        stopwatch.start()
                
                case "s":
                    if audio_process:
                        audio_pipe_father.send("audio_terminate")
                        audio_process.join()

                case "h":
                    print_app_msg(msg_queue, app_manual())

        except KeyboardInterrupt:
            main_pipe.send("stop")
            break

    if stopwatch:
        stopwatch.terminate()
        stopwatch.join()

    timer_process.join()

    if audio_process:
        audio_process.join()

    print_terminate(msg_queue)
    printer_process.join()

def get_key():
    """Lee una tecla de manera no bloqueante."""
    if select.select([sys.stdin], [], [], 0.1)[0]:
        key = sys.stdin.read(1)
        return key

    return None

def publish_notification(msgs):
    subprocess.run(["notify-send", *msgs, "-a", "cmd_pomodoro", "-t", "10"])

def finished_info_msg(args):
    summary_msg = "Finalizó el temporizador de {} minutos".format(args.minutes_count)
    if args.tag:
        summary_msg += " para la tarea {}.".format(args.tag)
    else:
        summary_msg += "."

    return [
            summary_msg,
            "Felicitaciones por el período de estudio! Te mereces un descanso."
            ]

def play_audio_on_subprocess(audio_track_path, audio_pipe):
    process = multiprocessing.Process(target=audio_process, args=(audio_track_path, audio_pipe))
    process.start()
    return process

def app_manual():
    manual = """
    Las opciones de teclas son:
    p   Pausar el temporizador
    c   Continuar con el temporizador
    f   Finalizar el temporizador
    t   Iniciar un stopwatch
    s   Detener la reproducción del sonido de finalización del timer
    h   Mostrar esta guía de comandos
    """
    return manual

def read_input():
    parser = build_parser()

    return parser.parse_args()

def build_parser():
    parser = argparse.ArgumentParser(
            description="""Es un programa que permite crear temporizadores que siguen 
            metodología pomodoro. Además lleva un registro de los pomodoros hechos
            e informa por medio de sonidos el estado del temporizador"""
            )
    
    parser.add_argument(
            "minutes_count",
            type=int,
            help="""Cantidad de minutos que debe durar el temporizador. Este es el 
            primer argumento posicional""",
            )

    parser.add_argument(
            "-tag", "-t",
            type=str,
            help="Tarea en la que se dedicó el tiempo del pomodoro."
            )

    parser.add_argument(
            "--test",
            action="store_true",
            help="Define la configuración a ser levantada como la de test",
            default=False
            )
    
    return parser

def load_config_from_file(args, file="config.ini"):
    if not os.path.exists(file):
        raise RuntimeError("The config file {} doesn't exists".format(file))
    
    env = "TEST" if args.test else "PRODUCTION"
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
            pomodoro_time= int(config_map["pomodoro_time"]),
            path_pc= config_map["path_pc"],
            between_pomodoros_sound= config_map["between_pomodoros_sound"],
            path_to_log= config_map["path_to_log"]
            )

@dc.dataclass(frozen=True)
class Config:
    pomodoro_time : int
    path_pc : str
    between_pomodoros_sound : str
    path_to_log : str

def write_config(file="config.ini", env="TEST"):
    config_object = ConfigParser()

    # Add server configuration to the config object
    config_object[env] = {
    "POMODORO_TIME": 1,
    "PATH_PC": "Scripts/temporizador_logger/audio/JAAA.mp3",
    "BETWEEN_POMODOROS_SOUND": "Scripts/temporizador_logger/audio/notification_sound_1.mp3",
    "PATH_TO_LOG": "Scripts/temporizador_logger/test/pomodoro_log.md"
    }

    with open('config.ini', 'a') as conf: 
        config_object.write(conf)

if __name__ == "__main__":
    main()
