#!/opt/cmd_pomodoro/pyenv/bin/python3

import time
from datetime import datetime, timedelta
import os
import sys
import multiprocessing
import subprocess
import select
import signal
import math
import pydub, simpleaudio, wave
from configparser import ConfigParser
import dataclasses as dc
import argparse
import curses
from enum import StrEnum, auto
from shutil import copy as shcopy
from pyfiglet import Figlet

CONFIGURATION_PATH = ".config/cmd_pomodoro"
TEMPORARY_PATH = ".cache/cmd_pomodoro"
DATA_PATH = ".local/share/cmd_pomodoro"

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

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def pomodoro_ended(seconds_since_last_pomodoro, pomodoro_duration_in_minutes):
    pomodoro_in_seconds = 60 * pomodoro_duration_in_minutes
    return seconds_since_last_pomodoro == pomodoro_in_seconds

##### stopwatch #####

def stopwatch_process(msg_queue):
    signal_handler = StopwatchSignalHandler()
    
    print_app_msg(msg_queue,"Temporizador iniciado")

    while signal_handler.KEEP_PROCESSING:
        time.sleep(1)
        signal_handler.SECONDS_COUNT += 1

    print_app_msg(msg_queue,"Temporizador duro: {}".format(stopwach_msg(signal_handler.SECONDS_COUNT)))

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

def audio_process(args, audio_path, audio_pipe):
    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = file_path_in_home(TEMPORARY_PATH, "timer_audio.wav")

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

def audio_process_short(args, audio_path):
    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = file_path_in_home(TEMPORARY_PATH, "pomo_audio.wav")

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

def print_app_msg(msg_queue, msg):
    _print(msg_queue, Msg(MsgType.App, msg))

def print_cmd_msg(msg_queue, msg):
    _print(msg_queue, Msg(MsgType.Cmd, msg))

def print_terminate(msg_queue):
    _print(msg_queue, Msg(MsgType.Termination, ""))

def _print(msg_queue, msg): # msg : Msg
    msg_queue.put(msg)

def printer(msg_queue):
    curses.wrapper(printer_display, msg_queue)

def printer_display(stdscr, msg_queue):
    # Configurar curses
    curses.curs_set(0)  # Ocultar el cursor
    stdscr.clear()

    # Obtener tamaño de la pantalla
    height, width = stdscr.getmaxyx()

    # Calcular dimensiones de las ventanas
    timer_height = height // 2
    command_input_height = 3
    manual_height = timer_height
    app_messages_height = timer_height - command_input_height

    timer_width = width
    manual_width = width // 2
    command_input_width = manual_width
    app_messages_width = manual_width

    # Crear ventanas
    timer_win = curses.newwin(timer_height, timer_width, 0, 0)
    manual_win = curses.newwin(manual_height, manual_width, timer_height, 0)
    command_input_win = curses.newwin(command_input_height, command_input_width, timer_height, manual_width)
    app_messages_win = curses.newwin(app_messages_height, app_messages_width, timer_height + command_input_height, manual_width)

    # Dibujar bordes y etiquetas iniciales
    manual_win.box()
    manual_win.addstr(0, 2, " Manual ")

    timer_win.box()
    timer_win.addstr(0, 2, " Tiempo para finalizar ")

    command_input_win.box()
    command_input_win.addstr(0, 2, " Comandos tipeados ")

    app_messages_win.box()
    app_messages_win.addstr(0, 2, " Mensajes de la aplicación ")

    # Refrescar ventanas
    timer_win.refresh()

    for index, line in enumerate(list(filter(None,app_manual().splitlines()))):
        manual_win.addstr(index+2, 1, line)
    manual_win.refresh()

    command_input_win.refresh()
    app_messages_win.refresh()

    last_state = {"time":"","app":[],"cmd":"","mode":Modes.Running} # TODO create State class
    lines = []
    timer_effect = []

    huge_letters = Figlet(font="standard")
    letters_start_position_y = timer_height // 3 + 2
    letters_start_position_x = timer_width // 3 + 7

    while True:
        while not msg_queue.empty():
            msg = msg_queue.get()

            if msg.kind == MsgType.Termination:
                return
            
            lines.append(msg)

        if not lines:
            state = last_state
        else:
            line = lines.pop()
            state = curr_state(line,last_state)


        if last_state["mode"] != state["mode"]:
            if state["mode"] == Modes.Stopped:
                timer_effect = stopped_effect()
            elif state["mode"] == Modes.Running:
                timer_effect = []
        else:
            timer_is_paused_and_effect_must_be_refilled = state["mode"] == Modes.Stopped and not timer_effect
            if timer_is_paused_and_effect_must_be_refilled:
                timer_effect = stopped_effect()
        
        if state["mode"] == Modes.Running:
            render_time(timer_win, timer_width, letters_start_position_y, letters_start_position_x, huge_letters, state["time"])
        else:
            render_time_with_effect(timer_effect,timer_win, timer_width, letters_start_position_y, letters_start_position_x, huge_letters, state["time"])
        timer_win.refresh()

        command_input_win.addstr(1, 1, "Último comando presionado: {}".format(state["cmd"]))
        command_input_win.refresh()

        for index, msg in enumerate(list(reversed(state["app"]))[:app_messages_height-2]):
            app_messages_win.addstr(index+1,1," " * (app_messages_width - 2))  # Limpiar la línea
            app_messages_win.addstr(index+1,1,msg)
        app_messages_win.refresh()


        last_state = state
        time.sleep(0.2)

def curr_state(msg, last_state):
    state = last_state
    match msg.kind:
        case MsgType.Time:
            state["time"] = msg.msg

        case MsgType.App:
            state["app"].append(msg.msg)

        case MsgType.Cmd:
            state["cmd"] = msg.msg
            if msg.msg == "p":
                state["mode"] = Modes.Stopped
            else:
                state["mode"] = Modes.Running

        case MsgType.Empty:
            pass

        case _:
            raise RuntimeError("msg {} unhandled".format(msg))

    return state

def render_time(timer_win, timer_win_width, start_pos_y, start_pos_x, figlet_render, time_str):
    numbers_splited = time_str.split(":")
    time = " : ".join(numbers_splited)
    figlet_str = figlet_render.renderText(time)
    
    for index, line in enumerate(figlet_str.splitlines()):
        timer_win.addstr(start_pos_y + index, 1, " " * (timer_win_width - 2))  # Limpiar la línea
        timer_win.addstr(start_pos_y + index, start_pos_x, line.rstrip())

def render_time_with_effect(timer_effect, timer_win, timer_win_width, start_pos_y, start_pos_x, figlet_render, time_str):
    effect = timer_effect.pop()
    if effect:
        render_time(timer_win, timer_win_width, start_pos_y, start_pos_x, figlet_render, time_str)
    else:
        timer_win.erase()
        timer_win.box()
        timer_win.addstr(0, 2, " Tiempo para finalizar ")

def stopped_effect():
    return [False,False,False,True,True,True]

@dc.dataclass(frozen=True)
class Msg:
    kind : str# kind : MsgType
    msg : str

class MsgType(StrEnum):
    Time = auto()
    App = auto()
    Cmd = auto()
    Termination = auto()
    Empty = auto()

class Modes(StrEnum):
    Running = auto()
    Stopped = auto()

##### main - keyboard manager #####

def main():
    args = read_input()
    if must_config(args):
        process_config(args)
        return

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
                audio_process = play_audio_on_subprocess(args, config.path_pc, audio_pipe_child)

            elif msg == "stoped":
                print_app_msg(msg_queue, "Relog apagado")
                break

            elif msg == "audio_pomodoro_finished":
                 (multiprocessing.Process(target=audio_process_short, args=(args, config.between_pomodoros_sound))).start()

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        if audio_process and audio_pipe_father.poll():
            msg = audio_pipe_father.recv()

            if msg == "audio_ended":
                print_app_msg(msg_queue, "Felicitaciones por el período de estudio! Te mereces un descanso.")
                time.sleep(2)
                break

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        try:
            key = get_key()
            match key:
                case "p":
                    print_cmd_msg(msg_queue,"p")
                    print_app_msg(msg_queue,"Cuenta atrás pausada.")
                    main_pipe.send("pause")

                case "c":
                    print_cmd_msg(msg_queue,"c")
                    print_app_msg(msg_queue,"Cuenta atrás reanudada.")
                    main_pipe.send("continue")

                case "f":
                    print_cmd_msg(msg_queue,"f")
                    main_pipe.send("stop")
                
                case "t":
                    print_cmd_msg(msg_queue,"t")
                    if stopwatch:
                        stopwatch.terminate()
                        stopwatch.join()
                        stopwatch = None
                    else:
                        stopwatch = multiprocessing.Process(target=stopwatch_process, args=(msg_queue,))
                        stopwatch.start()
                
                case "s":
                    print_cmd_msg(msg_queue,"s")
                    if audio_process:
                        audio_pipe_father.send("audio_terminate")
                        audio_process.join()

                case "h":
                    print_cmd_msg(msg_queue,"h")

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
    subprocess.run(["notify-send", *msgs, "-a", "cmd_pomodoro", "-t", "60"])

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

def play_audio_on_subprocess(args, audio_track_path, audio_pipe):
    process = multiprocessing.Process(target=audio_process, args=(args, audio_track_path, audio_pipe))
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
            e informa por medio de sonidos el estado del temporizador""",
            prog="cmd_pomodoro"
            )
    parser.add_argument(
            "--test", 
            action="store_true", 
            default=False,
            help="Define la configuración a ser levantada como la de test")

    subparser = parser.add_subparsers(
            dest="cmd", 
            title="Comandos",
            help="Tipea 'cmd --help' para obtener más información para cada comando")

    # main command
    timer_parser = subparser.add_parser("timer", help="Inicia un temporizador por la cantidad de minutos que se le provea como argumento.")
    timer_parser.add_argument(
            "minutes_count", 
            type=int, 
            help="Cantidad de minutos que debe durar el temporizador. Este es el primer argumento posicional")
    timer_parser.add_argument(
            "-tag", "-t", 
            type=str, 
            help="Tarea en la que se dedicó el tiempo del pomodoro.")

    # config command
    config_parser = subparser.add_parser(
            "config", 
            help="Definir toda la configuración relevante para el funcionamiento correcto del programa")
    config_parser.add_argument(
            "-pomodoro_time", 
            type=int, 
            metavar="minutos", 
            help="Duración de los pomodoros")
    config_parser.add_argument(
            "-finish_audio",
            type=str, 
            metavar="timer_audio",
            help="El audio que será reproducido al finalizar el temporizador. Debe ser un path absoluto al archivo.")
    config_parser.add_argument(
            "-intermediate_audio", 
            type=str,
            metavar="pomodoro_audio",
            help="El audio que será reproducido al finalizar cada pomodoro. Debe ser un path absoluto al archivo.")
    config_parser.add_argument(
            "-log_file", 
            type=str, 
            metavar="file",
            help="Archivo donde se anotarán los pomodoros terminados. Debe ser un path absoluto al archivo.")
    
    return parser

def must_config(args):
    return args.cmd and args.cmd == "config"

def process_config(args, file="config.ini"):
    config_object = read_config_file(args,file)

    env = "test" if args.test else "production"
    if env not in config_object:
        config_object.add_section(env)

    if args.pomodoro_time:
        config_object[env]["pomodoro_time"] = str(args.pomodoro_time)

    if args.finish_audio:
        new_path = copy_file_to_local_data(args.finish_audio, name_in_environment("finish_audio", env))
        config_object[env]["path_pc"] = new_path

    if args.intermediate_audio:
        new_path = copy_file_to_local_data(args.intermediate_audio, name_in_environment("intermediate_audio", env))
        config_object[env]["between_pomodoros_sound"] = new_path

    if args.log_file:
        config_object[env]["path_to_log"] = args.log_file

    with open(file_path_in_home(CONFIGURATION_PATH,file), 'w') as conf: 
        config_object.write(conf)

def copy_file_to_local_data(src_path, dst_name):
    return shcopy(file_path_in_home(src_path), file_path_in_home(DATA_PATH, dst_name))

def name_in_environment(file_name, env):
    return ".".join((file_name, env))

def read_config_file(args, file):
    file = file_path_in_home(CONFIGURATION_PATH, file)    

    config = ConfigParser()
    config.read(file)

    return config

def load_config_from_file(args, file="config.ini"):
    env = "test" if args.test else "production"

    config = read_config_file(args, file)

    return build_config(config[env])

def build_config(config_map):
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

def file_path(args, path, file_name):
    return os.path.join("", *[path,"test",file_name]) if args.test else os.path.join(path, file_name)

def file_path_env_agnostic(path, file_name):
    return os.path.join(path, file_name)

def file_path_in_home(*paths):
    return os.path.join(os.path.expanduser('~'), *paths)

if __name__ == "__main__":
    main()
