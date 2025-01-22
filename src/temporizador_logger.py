#!/opt/cmd_pomodoro/pyenv/bin/python3

import time
import sys
import multiprocessing
import subprocess
import select
from configparser import ConfigParser
import dataclasses as dc
import argparse
from shutil import copy as shcopy
import logging

from printer import printer
from stopwatch import stopwatch as stopwatch_process
from timer import timer, pomodoro
from process_audio import audio_process, audio_process_short
from utils import path_to_file, file_path_in_home, file_path_env_agnostic, file_path
from messages import *
from global_data import TEMPORARY_PATH, CONFIGURATION_PATH, DATA_PATH

def main():
    logging.basicConfig(
            level=logging.INFO,
            filename=file_path_in_home(TEMPORARY_PATH,"cmd_pomodoro.log"), 
            filemode="a+")
    logger = logging.getLogger(".main")
    logger.info("LOGGING SETTED UP")

    args = read_input()
    if must_config(args):
        process_config(args)
        return

    config = load_config_from_file(args=args)

    msg_queue = multiprocessing.Queue()
    printer_process = multiprocessing.Process(target=printer, args=(msg_queue,))
    printer_process.start()

    main_pipe, timer_pipe = multiprocessing.Pipe()
    timer_process = None
    can_pause = True
    if args.cmd == "timer":
        timer_process = multiprocessing.Process(
                target=timer, 
                args=(
                    timer_pipe, 
                    args.minutes_count, 
                    args.tag, 
                    config.path_to_log, 
                    config.pomodoro_time, 
                    msg_queue))

    elif args.cmd == "pomodoro":
        timer_process = multiprocessing.Process(
                target=pomodoro,
                args=(timer_pipe,
                      args.pomodoros,
                      args.tag,
                      config.pomodoro_time,
                      config.pomodoro_break_duration,
                      config.path_to_log,
                      msg_queue)) 
        can_pause = False
    else:
        raise RuntimeError("Comando {} desconocido")

    timer_process.start()

    audio_pipe_father, audio_pipe_child = multiprocessing.Pipe()
    audio_process = None

    stopwatch = None

    paused = False

    while True:
        if main_pipe.poll():
            msg = main_pipe.recv()

            if msg == "finished":
                publish_notification(finished_info_msg(args))
                event_playback(msg_queue)
                audio_process = play_audio_on_subprocess(args, config.path_pc, audio_pipe_child)

            elif msg == "stopped":
                print_app_msg(msg_queue, "Relog apagado")
                break

            elif msg == "audio_pomodoro_finished":
                event_playback(msg_queue)
                (multiprocessing.Process(target=audio_process_short, args=(args, config.between_pomodoros_sound, msg_queue))).start()

            elif msg == "audio_break_ended":
                event_playback(msg_queue)
                (multiprocessing.Process(target=audio_process_short, args=(args, config.audio_pomodoro_break_finish, msg_queue))).start()

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        if audio_process and audio_pipe_father.poll():
            msg = audio_pipe_father.recv()

            if msg == "audio_ended":
                event_audio_stopped(msg_queue)
                print_app_msg(msg_queue, "Felicitaciones por el período de estudio! Te mereces un descanso.")
                time.sleep(2)
                break

            else:
                raise RuntimeError(f"Message {msg} is unhandled by main process")

        try:
            key = get_key()
            match key:
                case "p":
                    if paused:
                        continue

                    if not can_pause:
                        continue

                    paused = True
                    print_cmd_msg(msg_queue,"p")
                    event_stopped(msg_queue)
                    print_app_msg(msg_queue,"Cuenta atrás pausada.")
                    main_pipe.send("pause")

                case "c":
                    if not paused:
                        continue

                    paused = False
                    print_cmd_msg(msg_queue,"c")
                    event_resumed(msg_queue)
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
                    if audio_process:
                        print_cmd_msg(msg_queue,"s")
                        audio_pipe_father.send("audio_terminate")
                        audio_process.join()

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
    if args.cmd == "timer":
        summary_msg = "Finalizó el temporizador de {} minutos".format(args.minutes_count)
    else:
        summary_msg = "Finalizaron los {} pomodoros".format(args.pomodoros)

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

    # timer command
    timer_parser = subparser.add_parser("timer", help="Inicia un temporizador por la cantidad de minutos que se le provea como argumento.")
    timer_parser.add_argument(
            "minutes_count", 
            type=int, 
            default=None,
            help="Cantidad de minutos que debe durar el temporizador. Este es el primer argumento posicional")
    timer_parser.add_argument(
            "-tag", "-t", 
            type=str, 
            default=None,
            help="Tarea en la que se dedicó el tiempo del pomodoro.")

    # pomodoro command
    pomodoro_parser = subparser.add_parser("pomodoro", help="Comienza tantos pomodoros como se pase por argumento.")
    pomodoro_parser.add_argument(
            "pomodoros", 
            type=int, 
            metavar="amount_of_pomodoros",
            help="Cantidad de pomodoros que se quiere realizar. Al final de cada intervalo habrá un periodo de descanso.")
    pomodoro_parser.add_argument(
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
            "-pomodoro_break_duration", 
            type=int, 
            metavar="minutos",
            help="La duración del receso luego de cada pomodoro.")
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
            "-break_finish_audio", 
            type=str,
            metavar="finish_break_audio",
            help="El audio que será reproducido al finalizar cada descanso post pomodoro. Debe ser un path absoluto al archivo.")
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

    if args.pomodoro_break_duration:
        config_object[env]["pomodoro_break_duration"] = str(args.pomodoro_break_duration)

    if args.finish_audio:
        new_path = copy_file_to_local_data(args.finish_audio, name_in_environment("finish_audio", env))
        config_object[env]["path_pc"] = new_path

    if args.intermediate_audio:
        new_path = copy_file_to_local_data(args.intermediate_audio, name_in_environment("intermediate_audio", env))
        config_object[env]["between_pomodoros_sound"] = new_path

    if args.break_finish_audio:
        new_path = copy_file_to_local_data(args.break_finish_audio, name_in_environment("break_finish_audio", env))
        config_object[env]["audio_pomodoro_break_finish"] = new_path

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
            pomodoro_break_duration= int(config_map["pomodoro_break_duration"]),
            path_pc= config_map["path_pc"],
            between_pomodoros_sound= config_map["between_pomodoros_sound"],
            audio_pomodoro_break_finish= config_map["audio_pomodoro_break_finish"],
            path_to_log= config_map["path_to_log"]
            )

@dc.dataclass(frozen=True)
class Config:
    pomodoro_time : int
    pomodoro_break_duration : int
    path_pc : str
    between_pomodoros_sound : str
    audio_pomodoro_break_finish : str
    path_to_log : str

if __name__ == "__main__":
    main()
