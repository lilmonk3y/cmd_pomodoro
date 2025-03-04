#!/opt/cmd_pomodoro/venv/bin/python3

import time
import sys
import multiprocessing
import subprocess
import select
import logging

from printer import printer
from stopwatch import stopwatch as stopwatch_process
from timer import timer, pomodoro
from process_audio import audio_process, audio_process_short
from utils import file_path_in_home, verify_config_and_args 
from messages import *
from global_data import TEMPORARY_PATH 
from input_parser import read_input, must_config, process_config, load_config_from_file

def main():
    args = read_input()
    if must_config(args):
        process_config(args)
        return

    config = load_config_from_file(args=args)

    verify_config_and_args(args, config)
    
    _init_logger(args)

    EventBrokerManager.register("EventBroker", EventBroker)
    with EventBrokerManager() as manager:
        msg_queue = manager.EventBroker()
        (Main(args=args, config=config, msg_queue=msg_queue)).run()

class Main:
    def __init__(self, args, config, msg_queue):
        self._args = args
        self._config = config
        self._msg_queue = msg_queue

        self._msg_queue_pipe = self._msg_queue.suscribe(*[event for event in Event], suscriber=getpid())

        self._can_pause = config.can_pause_pomodoros
        self._paused = False
        self._must_finish = False
        self._in_input_state = False

        self._audio_process = None
        self._stopwatch_process = None
        self._printer_process = self._start_printer()
        self._timer_process = self._start_timer()

    def run(self):
        try:
            while not self._must_finish:
                self._poll_events()

                self._handle_cmds_pressed_if_any()

        except KeyboardInterrupt:
            self._finish_unsuccessfully()

        self._finish_gracefully()

    def _start_printer(self):
        printer_process = multiprocessing.Process(
                    target=printer, 
                    args=(self._msg_queue,self._config.tags))
        printer_process.start()
        return printer_process

    def _start_timer(self):
        if self._args.cmd == "timer":
            event_timer_init(self._msg_queue)
            self._can_pause = True
            timer_process = multiprocessing.Process(
                    target=timer, 
                    args=(self._args.minutes_count, 
                          self._args.tag, 
                          self._config.path_to_log, 
                          self._config.pomodoro_time, 
                          self._msg_queue,
                          self._args.purpose))

        elif self._args.cmd == "pomodoro":
            event_pomodoro_init(self._msg_queue)
            timer_process = multiprocessing.Process(
                    target=pomodoro,
                    args=(self._args.pomodoros,
                          self._args.tag,
                          self._config.pomodoro_time,
                          self._config.pomodoro_break_duration,
                          self._config.path_to_log,
                          self._msg_queue,
                          self._args.purpose)) 

        else:
            raise RuntimeError("Comando {} desconocido")

        timer_process.start()

        return timer_process

    def _poll_events(self):
        while self._msg_queue_pipe.poll():
            msg = self._msg_queue_pipe.recv()
            match msg.kind:
                case Event.Termination:
                    print_app_msg(self._msg_queue, "Relog apagado")
                    self._must_finish = True

                case Event.TimerFinished:
                    publish_notification(finished_info_msg(self._args))
                    event_playback(self._msg_queue)
                    self._audio_process = play_audio_on_subprocess(self._args, self._config.path_pc, self._msg_queue)
                    event_stop_stopwatch(self._msg_queue)

                case Event.AudioPomodoroFinished:
                    event_playback(self._msg_queue)
                    (multiprocessing.Process(
                        target=audio_process_short, 
                        args=(
                            self._args, 
                            self._config.between_pomodoros_sound, 
                            self._msg_queue))).start()

                case Event.BreakFinished:
                    event_playback(self._msg_queue)
                    (multiprocessing.Process(
                        target=audio_process_short, 
                        args=(
                            self._args, 
                            self._config.audio_pomodoro_break_finish, 
                            self._msg_queue))).start()

                case Event.AudioEnded:
                    event_audio_stopped(self._msg_queue)
                    print_app_msg(self._msg_queue, "Felicitaciones por el período de estudio! Te mereces un descanso.")
                    event_terminate(self._msg_queue)
                    self._must_finish = True
                    time.sleep(2)

                case Event.PurposeFinished | Event.TagFinished:
                    self._in_input_state = False

                case _:
                    pass

    def _handle_cmds_pressed_if_any(self):
        if not self._get_input_keys():
            return

        key = get_key()
        match key:
            case "p":
                if not self._can_pause:
                    return

                print_cmd_msg(self._msg_queue,"p")

                if not self._paused:
                    self._paused = True
                    event_stop_timer(self._msg_queue)
                else:
                    self._paused = False
                    event_resume_timer(self._msg_queue)

            case "f":
                print_cmd_msg(self._msg_queue,"f")
                if self._audio_process:
                    event_audio_terminate(self._msg_queue)
                    self._audio_process.join()
                else:
                    event_terminate(self._msg_queue)
            
            case "t":
                print_cmd_msg(self._msg_queue,"t")
                if self._stopwatch_process:
                    event_stop_stopwatch(self._msg_queue)
                    self._stopwatch_process.join()
                    self._stopwatch_process = None
                else:
                    self._stopwatch_process = multiprocessing.Process(
                        target=stopwatch_process, 
                        args=(self._msg_queue,))
                    self._stopwatch_process.start()
            
            case "i":
                print_cmd_msg(self._msg_queue, "i")
                event_add_purpose(self._msg_queue)
                self._in_input_state = True

            case "r":
                print_cmd_msg(self._msg_queue, "r")
                event_tag_change(self._msg_queue)
                self._in_input_state = True
            
            case _:
                pass

    def _get_input_keys(self):
        return not self._in_input_state

    def _finish_gracefully(self):
        self._timer_process.join()

        if self._stopwatch_process:
            self._stopwatch_process.join()

        if self._audio_process:
            self._audio_process.join()

        event_stop_printer(self._msg_queue)
        self._printer_process.join()

        self._msg_queue.unsuscribe(getpid(), [event for event in Event])

    def _finish_unsuccessfully(self):
        #event_terminate(self._msg_queue)

        self._printer_process.terminate()
        self._timer_process.terminate()

        if self._stopwatch_process:
            self._stopwatch_process.terminate()

        if self._audio_process:
            self._audio_process.terminate()

        self._msg_queue.unsuscribe(getpid(), [event for event in Event])

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

def play_audio_on_subprocess(args, audio_track_path, msg_queue):
    process = multiprocessing.Process(target=audio_process, args=(args, audio_track_path, msg_queue))
    process.start()
    return process

def _init_logger(args):
    logging.basicConfig(
            level=logging.DEBUG if args.debug else logging.INFO,
            filename=file_path_in_home(TEMPORARY_PATH,"cmd_pomodoro.log"), 
            filemode="a+")
    logger = logging.getLogger(".main")
    logger.info("LOGGING SETTED UP")

if __name__ == "__main__":
    main()
