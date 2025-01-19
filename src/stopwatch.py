import time
import signal
import math

from messages import print_app_msg

def stopwatch(msg_queue):
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
