import argparse
from configparser import ConfigParser
import dataclasses as dc
from shutil import copy as shcopy

from utils import file_path_in_home  
from global_data import CONFIGURATION_PATH, DATA_PATH

def read_input():
    parser = _build_parser()

    return parser.parse_args()

def must_config(args):
    return args.cmd and args.cmd == "config"

def load_config_from_file(args, file="config.ini"):
    env = "test" if args.test else "production"

    config = _read_config_file(args, file)

    return _build_config(config[env])

def process_config(args, file="config.ini"):
    config_object = _read_config_file(args,file)

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

    if args.can_pause_pomodoros:
        can_pause_pomodoros = args.can_pause_pomodoros == "Y" 
        config_object[env]["can_pause_pomodoros"] = str(can_pause_pomodoros)

    if args.tag_add:
        tags = config_object.getlist(env, "tags") if config_object.has_option(env, "tags") else []
        tags_modified = False
        for tag in args.tag_add.split(','):
            if tag not in tags:
                tags.append(tag)
                tags_modified = True
        if tags_modified:
            config_object[env]["tags"] = write_list(tags)

    if args.tag_delete:
        tags = config_object.getlist(env, "tags") if config_object.has_option(env, "tags") else []
        if args.tag_delete in tags:
            tags = [tag for tag in tags if tag != args.tag_delete]
            config_object[env]["tags"] = write_list(tags)

    path_to_config_file = file_path_in_home(CONFIGURATION_PATH,file)

    with open(path_to_config_file, 'w') as conf: 
        config_object.write(conf)

    if args.show:
        with open(path_to_config_file, 'r') as f:
            content = f.read()
            print(content)

def _build_parser():
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

    parser.add_argument(
            "--debug", 
            action="store_true", 
            default=False,
            help="Se configuran los logs para imprimir más información relevante para debugging")

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
    timer_parser.add_argument(
            "-purpose", "-p", 
            type=str, 
            default=None,
            help="Intención u objetivo que se quiere cumplir en este pomodoro")

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
    pomodoro_parser.add_argument(
            "-purpose", "-p", 
            type=str, 
            default=None,
            help="Intención u objetivo que se quiere cumplir en este pomodoro.")

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
    config_parser.add_argument(
            "-can_pause_pomodoros", 
            type=str, 
            metavar="can_pause_pomodoros",
            help="Indica si los pomodoros pueden ser pausados una vez comenzados. Los valores para esta opción son 'Y' o 'N'.")
    config_parser.add_argument(
            "-tag_add", 
            type=str, 
            help="Un nuevo tag para la lista de tags válidos.")
    config_parser.add_argument(
            "-tag_delete", 
            type=str, 
            help="Un tag que se debe eliminar de la lista de tags válidos.")
    config_parser.add_argument(
            "--show", 
            action="store_true", 
            default=False,
            help="Imprime el contenido del archivo de configuración luego de haber corrido las actualizaciones correspondientes.")
    
    return parser

def copy_file_to_local_data(src_path, dst_name):
    return shcopy(file_path_in_home(src_path), file_path_in_home(DATA_PATH, dst_name))

def name_in_environment(file_name, env):
    return ".".join((file_name, env))

def _read_config_file(args, file):
    file = file_path_in_home(CONFIGURATION_PATH, file)    

    config = ConfigParser(
        converters={
            'list': read_list
        }) # allow getlist on config file
    config.read(file)

    return config

def read_list(string):
    return [i.strip() for i in string.split(',')] if len(string) > 0 else []

def write_list(list):
    return ','.join(list)

def _build_config(config_map):
    fields = dc.fields(Config)
    field_keys = list(map(lambda f: f.name, fields))
    keys = list(config_map.keys())
    if not set(keys).issubset(field_keys):
        raise RuntimeError("There are missing keys in the config file. Expected keys: {}. Actual keys: {}".format(field_keys, keys))

    return Config(
            pomodoro_time= config_map.getint("pomodoro_time"),
            pomodoro_break_duration= config_map.getint("pomodoro_break_duration"),
            path_pc= config_map["path_pc"],
            between_pomodoros_sound= config_map["between_pomodoros_sound"],
            audio_pomodoro_break_finish= config_map["audio_pomodoro_break_finish"],
            path_to_log= config_map["path_to_log"],
            can_pause_pomodoros= config_map.getboolean("can_pause_pomodoros"),
            tags= config_map.getlist("tags")
            )

@dc.dataclass(frozen=True)
class Config:
    pomodoro_time : int
    pomodoro_break_duration : int
    path_pc : str
    between_pomodoros_sound : str
    audio_pomodoro_break_finish : str
    path_to_log : str
    can_pause_pomodoros : bool
    tags : list[str]
