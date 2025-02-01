import math
from os import getpid
from time import sleep

from messages import print_app_msg, Event

def stopwatch(msg_queue):
    (Stopwatch(msg_queue)).run()

class Stopwatch:
    def __init__(self, msg_queue):
        self._seconds = 0
        self._must_exit = False
        self._msg_queue = msg_queue
        self._pipe = msg_queue.suscribe(Event.Termination, Event.StopStopwatch, suscriber=getpid())

    def run(self):
        print_app_msg(self._msg_queue,"Temporizador iniciado")

        while not self._must_exit:
            self._poll_msgs()
            self._seconds += 1
            sleep(1)

        print_app_msg(self._msg_queue,"Temporizador duro: {}".format(stopwach_msg(self._seconds)))


    def _poll_msgs(self):
        while self._pipe.poll():
            msg = self._pipe.recv()
            match msg.kind:
                case Event.Termination | Event.StopStopwatch:
                    self._must_exit = True

def stopwach_msg(seconds):
    minutes = math.ceil(seconds/60)
    return f"{minutes} minutos" if minutes != 1 else f"{minutes} minuto"


