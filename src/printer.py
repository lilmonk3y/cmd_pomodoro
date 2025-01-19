from abc import abstractmethod, ABC
from typing import Any
from pyfiglet import Figlet
from enum import StrEnum, auto
import curses
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from messages import MsgType, Msg, Event

def printer(msg_queue):
    curses.wrapper(printer_display, msg_queue)

def printer_display(stdscr, msg_queue):
    logger = logging.getLogger(".printer")

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

    init_state = {"time":"","app":[],"cmd":"","mode":Modes.Running} # TODO create State class
    (Printer(
        CommandInputWindow(
            window=command_input_win,
            width=command_input_width,
            height=command_input_height
            ),
        AppMessagesWindow(
            window=app_messages_win,
            width=app_messages_width,
            height=app_messages_height
            ),
        TimerWindow(
            window=timer_win,
            width=timer_width,
            height=timer_height
            )
        )).run( 
               state = init_state, 
               msg_queue=msg_queue
               )

class Window:
    def __init__(self, window, width, height):
        self.window = window
        self.width = width
        self.height = height

    def refresh(self, last_state, state):
        raise RuntimeError("Shouldn't be used")

    def _refresh(self):
        self.window.refresh()

class TimerWindow(Window):
    def __init__(self,window, width, height):
        super().__init__(window, width, height)

        self._text_effect = NoneTextEffect()
        self._figlet = Figlet(font="standard")

        self._start_y = height // 3 + 2
        self._start_x = width // 3 + 7

        self._logger = logging.getLogger(".timer_window")

    def refresh(self, last_state, state):
        if last_state["mode"] != state["mode"]:
            if state["mode"] == Modes.Stopped:
                self._text_effect = BlinkTextEffect()

            elif state["mode"] == Modes.AudioPlayback:
                self._text_effect = SlideTextEffect()

            elif state["mode"] == Modes.Running:
                self._text_effect = NoneTextEffect()

            else:
                raise RuntimeError("Mode {} is unhandled".format(state["mode"]))

        else:
            if self._text_effect.empty():
                self._text_effect.refill()
        
        self._text_effect.render(TimerRenderInput(
            window=self.window, 
            window_width=self.width, 
            start_y=self._start_y, 
            start_x=self._start_x, 
            figlet_render=self._figlet, 
            time_str=self._figlet_readable_str(state["time"])))

        self._refresh()

    def _figlet_readable_str(self, time_str):
        numbers_splited = time_str.split(":")
        return " : ".join(numbers_splited)

class AppMessagesWindow(Window):
    def refresh(self, _, state):
        for index, msg in enumerate(list(reversed(state["app"]))[:self.height-2]):
            self.window.addstr(index+1,1," " * (self.width - 2))  # Limpiar la línea
            self.window.addstr(index+1,1,msg)

        self._refresh()

class CommandInputWindow(Window):
    def refresh(self, _, state):
        self.window.addstr(1, 1, "Último comando presionado: {}".format(state["cmd"]))

        self._refresh()

class Printer:
    def __init__(self, *windows):
        self._windows = windows
        self._must_update = datetime.now()
        self._must_finish = False
        self._logger = logging.getLogger(".printer")
        self._last_state_refreshed = None

    def run(self, state, msg_queue):
        self._last_state_refreshed = dict(state)
        last_state = dict(state)

        while True and not self._must_finish:
            new_state = self._process_new_msgs(msg_queue, last_state)

            self._refresh_if_have_to(new_state)

            last_state = dict(new_state)

    def _process_new_msgs(self, msg_queue, last_state):
        state = dict(last_state)

        while not msg_queue.empty():
            msg = msg_queue.get()

            if msg.kind == MsgType.Termination:
                self._must_finish = True
                return state
            
            state = self._curr_state(msg, state)

        return state

    def _refresh_if_have_to(self, state):
        if not self._time_is_up():
            return
        
        for window in self._windows:
            window.refresh(self._last_state_refreshed, state)

        self._last_state_refreshed = dict(state)
        self._set_next_update()

    def _curr_state(self, msg, last_state):
        state = dict(last_state)
        match msg.kind:
            case MsgType.Time:
                state["time"] = msg.msg

            case MsgType.App:
                state["app"].append(msg.msg)

            case MsgType.Cmd:
                state["cmd"] = msg.msg

            case MsgType.Event:
                match msg.msg:
                    case Event.AudioPlayback:
                        state["mode"] = Modes.AudioPlayback

                    case Event.Stopped:
                        state["mode"] = Modes.Stopped

                    case Event.AudioStopped | Event.Resumed:
                        state["mode"] = Modes.Running

                    case _:
                        raise RuntimeError("Event {} unhandled".format(msg.msg))

            case MsgType.Empty:
                pass

            case _:
                raise RuntimeError("msg {} unhandled".format(msg))

        return state
    
    def _time_is_up(self):
        return self._must_update < datetime.now()

    def _set_next_update(self):
        self._must_update = datetime.now() + timedelta(seconds=0.5)

class TextEffect(ABC):
    @abstractmethod
    def empty(self):
        pass

    @abstractmethod
    def refill(self):
        pass

    @abstractmethod
    def render(self, timer_render_obj):
        pass

class NoneTextEffect(TextEffect):
    def __init__(self):
        self._logger = logging.getLogger(".none_text_effect")

    def empty(self):
        return False

    def refill(self):
        pass

    def render(self, timer_render_obj):
        render_time(timer_render_obj)

class SlideTextEffect(TextEffect):
    def __init__(self):
        self._logger = logging.getLogger(".slide_text_effect")
        self._fill()
        self._position_to_affect = 0

    def empty(self):
        return self._period == []

    def refill(self):
        self._fill()

    def render(self, timer_render_obj):
        frame = self._frame()
        if frame:
            timer_render_obj.time_str = self._slide_effect(timer_render_obj.time_str)
            render_time(timer_render_obj)
        else:
            render_time(timer_render_obj)

    def _slide_effect(self, time_str):
        res = list(time_str)

        self._find_next_non_empty_position(res)
        res[self._position_to_affect] = '*'
        self._position_to_affect = (self._position_to_affect + 1) % len(time_str)
        
        return "".join(res)
    
    def _frame(self):
        return self._period.pop()

    def _fill(self):
        self._period = [True,False]

    def _find_next_non_empty_position(self, chr_list):
        for index in range(self._position_to_affect, len(chr_list)):
            elem = chr_list[index]
            if elem != " " and elem != ":":
                self._position_to_affect = index
                return

        # No empty char. update to begining
        self._position_to_affect = 0

class BlinkTextEffect(TextEffect):
    def __init__(self):
        self._logger = logging.getLogger(".blink_text_effect")
        self._fill()

    def empty(self):
        return self._period == []

    def refill(self):
        self._fill()

    def render(self, timer_render_obj):
        frame = self._frame()
        if frame:
            render_time(timer_render_obj)
        else:
            timer_render_obj.window.erase()
            timer_render_obj.window.box()
            timer_render_obj.window.addstr(0, 2, " Tiempo para finalizar ")

    def _frame(self):
        return self._period.pop()

    def _fill(self):
        self._period = [False,True]

def render_time(timer_obj):
    figlet_str = timer_obj.figlet_render.renderText(timer_obj.time_str)

    for index, line in enumerate(figlet_str.splitlines()):
        timer_obj.window.addstr( timer_obj.start_y + index, 1, 
                " " * (timer_obj.window_width - 2))  # Limpiar la línea
        timer_obj.window.addstr(
                timer_obj.start_y + index, 
                timer_obj.start_x, 
                line.rstrip())

@dataclass
class TimerRenderInput():
    window : Any
    window_width : int
    start_y : int
    start_x : int
    figlet_render : Any
    time_str : str

class Modes(StrEnum):
    Running = auto()
    Stopped = auto()
    AudioPlayback = auto()

def app_manual():
    manual = """
    Las opciones de teclas son:
    p   Pausar el temporizador
    c   Continuar con el temporizador
    f   Finalizar el temporizador
    t   Iniciar un stopwatch
    s   Detener la reproducción del sonido de finalización del timer
    """
    return manual

