#!/opt/cmd_pomodoro/pyenv/bin/python3

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
from utils import file_path_in_home 
from messages import *
from global_data import TEMPORARY_PATH 
from input_parser import read_input, must_config, process_config, load_config_from_file

def main():
    _init_logger()

    args = read_input()
    if must_config(args):
        process_config(args)
        return

    config = load_config_from_file(args=args)

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

        self._audio_process = None
        self._stopwatch = None

        self._can_pause = True
        self._paused = False
        self._must_finish = False

        self._start_printer()
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
        self.printer_process = multiprocessing.Process(
                    target=printer, 
                    args=(self._msg_queue,))
        self.printer_process.start()

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
                          self._msg_queue))

        elif self._args.cmd == "pomodoro":
            event_pomodoro_init(self._msg_queue)
            self._can_pause = False
            timer_process = multiprocessing.Process(
                    target=pomodoro,
                    args=(self._args.pomodoros,
                          self._args.tag,
                          self._config.pomodoro_time,
                          self._config.pomodoro_break_duration,
                          self._config.path_to_log,
                          self._msg_queue)) 

        else:
            raise RuntimeError("Comando {} desconocido")

        timer_process.start()

        return timer_process

    def _poll_events(self):
        while self._msg_queue_pipe.poll():
            msg = self._msg_queue_pipe.recv()
            match msg.kind:
                case Event.TimerFinished:
                    publish_notification(finished_info_msg(self._args))
                    event_playback(self._msg_queue)
                    self._audio_process = play_audio_on_subprocess(self._args, self._config.path_pc, self._msg_queue)

                case Event.TimerStopped:
                    print_app_msg(self._msg_queue, "Relog apagado")
                    self._must_finish = True

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
                    time.sleep(2)
                    self._must_finish = True

                case _:
                    pass

    def _handle_cmds_pressed_if_any(self):
        key = get_key()
        match key:
            case "p":
                if self._paused:
                    return

                if not self._can_pause:
                    return

                self._paused = True
                print_cmd_msg(self._msg_queue,"p")
                event_stopped(self._msg_queue)
                print_app_msg(self._msg_queue,"Cuenta atrás pausada.")

            case "c":
                if not self._paused:
                    return

                self._paused = False
                print_cmd_msg(self._msg_queue,"c")
                event_resumed(self._msg_queue)
                print_app_msg(self._msg_queue,"Cuenta atrás reanudada.")

            case "f":
                print_cmd_msg(self._msg_queue,"f")
                event_stop_timer(self._msg_queue)
            
            case "t":
                print_cmd_msg(self._msg_queue,"t")
                if self._stopwatch:
                    self._stopwatch.terminate()
                    self._stopwatch.join()
                    self._stopwatch = None
                else:
                    self._stopwatch = multiprocessing.Process(
                        target=stopwatch_process, 
                        args=(self._msg_queue,))
                    self._stopwatch.start()
            
            case "s":
                if self._audio_process:
                    print_cmd_msg(self._msg_queue,"s")
                    event_audio_terminate(self._msg_queue)
                    self._audio_process.join()
            
            case _:
                pass

    def _finish_gracefully(self):
        event_stop_timer(self._msg_queue)

        if self._stopwatch:
            self._stopwatch.terminate()
            self._stopwatch.join()

        self._timer_process.join()

        if self._audio_process:
            self._audio_process.join()

        print_terminate(self._msg_queue)
        self.printer_process.join()
        self._msg_queue.unsuscribe(getpid(), [event for event in Event])

    def _finish_unsuccessfully(self):
        event_stop_timer(self._msg_queue)
        # self._timer_process.terminate()

        if self._stopwatch:
            self._stopwatch.terminate()

        if self._audio_process:
            self._audio_process.terminate()

        self.printer_process.terminate()
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

def _init_logger():
    logging.basicConfig(
            level=logging.INFO,
            filename=file_path_in_home(TEMPORARY_PATH,"cmd_pomodoro.log"), 
            filemode="a+")
    logger = logging.getLogger(".main")
    logger.info("LOGGING SETTED UP")

if __name__ == "__main__":
    main()
