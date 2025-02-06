from abc import abstractmethod, ABC
from typing import Any
from pyfiglet import Figlet
import curses
from curses import textpad
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from os import getpid
import signal

from messages import *

def printer(msg_queue, tags):
    curses.wrapper(printer_display, msg_queue, tags)

def printer_display(stdscr, msg_queue, tags):
    global _msg_queue 
    _msg_queue = msg_queue

    # Configurar curses
    curses.curs_set(0)  # Ocultar el cursor
    stdscr.clear()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)

    # Obtener tamaño de la pantalla
    height, width = stdscr.getmaxyx()

    (Screen(
        build_main_layout(height,width),
        build_input_layout(height,width),
        build_tag_input_layout(height,width,tags),
        screen=stdscr
     )).run()

def build_main_layout(height,width):
    layout = main_layout(height,width)

    height_offset = layout["timer_height"] + layout["status_bar_height"]

    return Layout(
            StatusBarTile(
                window=curses.newwin(layout["status_bar_height"], layout["status_bar_width"], 0, 0),
                width=layout["status_bar_width"],
                height=layout["status_bar_height"]),
            TimerTile(
                window=curses.newwin(layout["timer_height"], layout["timer_width"], layout["status_bar_height"], 0),
                width=layout["timer_width"],
                height=layout["timer_height"]
                ),
            ManualTile(
                window=curses.newwin(layout["manual_height"], layout["manual_width"], height_offset, 0),
                width=layout["manual_width"],
                height=layout["manual_height"]),
            CommandInputTile(
                window=curses.newwin(layout["command_input_height"], layout["command_input_width"], height_offset, layout["manual_width"]),
                width=layout["command_input_width"],
                height=layout["command_input_height"]
                ),
            AppMessagesTile(
                window=curses.newwin(layout["app_messages_height"], layout["app_messages_width"], height_offset + layout["command_input_height"], layout["manual_width"]),
                width=layout["app_messages_width"],
                height=layout["app_messages_height"])
    )

def main_layout(height, width):
    timer_height = (height // 2)
    status_bar_height = 3
    command_input_height = 3
    manual_width = (width // 2)

    return dict({
    "timer_height": (height // 2),
    "status_bar_height" : 3,
    "command_input_height" : 3,
    "manual_height" : (timer_height - status_bar_height),
    "app_messages_height" : (timer_height - command_input_height - status_bar_height),

    "timer_width" : (width),
    "status_bar_width" : (width),
    "manual_width" : (width // 2),
    "command_input_width" : (manual_width),
    "app_messages_width" : (manual_width)
    })

def build_input_layout(height, width):
    layout = input_layout(height, width)
    window = curses.newwin(layout["win_height"],layout["win_width"], height//3, width//2 //2)

    return Layout(
            PurposeInputTile(
                window=window,
                width=layout["win_width"],
                height=layout["win_height"]))

def input_layout(height, width):
    return dict({
        "win_height" : (height // 3),
        "win_width" : (width // 2)
    })

def build_tag_input_layout(height, width, tags):
    layout = tag_input_layout(height, width)
    
    window = curses.newwin(layout["win_height"], layout["win_width"], height//3, width//3)

    return Layout(
            TagInputTile(
                window=window,
                width=layout["win_width"],
                height=layout["win_height"],
                tags=tags))

def tag_input_layout(height, width):
    return dict({
        "win_height" : (height // 3),
        "win_width" : (width // 3)
    })

class Screen:
    def __init__(self, *layouts, screen):
        self._layouts = layouts
        self._must_update = datetime.now()
        self._must_finish = False
        self._screen = screen

        self._msgs_pipe = _msg_queue.suscribe(*[event for event in Event],suscriber=getpid())
        signal.signal(signal.SIGWINCH, self._resize_event)
        self._logger = logging.getLogger(".printer")

    def run(self):
        self._draw_layout()
        event_printer_ready(_msg_queue)

        while not self._must_finish:
            self._pool_for_msgs()
            self._refresh_if_have_to()
            
        _msg_queue.unsuscribe(getpid(), [event for event in Event])

    def _pool_for_msgs(self):
        while self._msgs_pipe.poll():
            msg = self._msgs_pipe.recv()

            self._logger.info("Printer is consuming msg {}".format(msg))

            if msg.kind == Event.StopPrinter:
                self._must_finish = True
                _msg_queue.unsuscribe(getpid(), [event for event in Event])
                return

            if msg.kind == Event.LayoutDraw:
                self._draw_layout()

            for layout in self._layouts:
                layout.process(msg)

    def _draw_layout(self):
        for layout in self._layouts:
            layout.draw()

    def _refresh_if_have_to(self):
        if not self._time_is_up():
            return
        
        for layout in self._layouts:
            layout.refresh()

        self._set_next_update()

    def _time_is_up(self):
        return self._must_update < datetime.now()

    def _set_next_update(self):
        self._must_update = datetime.now() + timedelta(seconds=0.5)

    def _resize_event(self, signum, frame):
        height, width = self._screen.getmaxyx()
        # curses.resize_term(0,0)
        curses.resize_term(height,width)
        curses.resizeterm(height, width)
        for layout in self._layouts:
            layout.resize(height, width)

class Layout:
    def __init__(self, *tiles): #: [Tile]
        self._tiles = tiles

    def draw(self):
        self._tiles_do(lambda window: window.draw())

    def refresh(self):
        self._tiles_do(lambda window: window.refresh())

    def process(self, msg):
        self._tiles_do(lambda window: window.process(msg))

    def resize(self, height, width):
        self._tiles_do(lambda window: window.resize(height, width))

    def _tiles_do(self, func):
        for tile in self._tiles:
            func(tile)

class Tile(ABC):
    def __init__(self, window, width, height):
        self.window = window
        self.width = width
        self.height = height

    @abstractmethod
    def process(self, msg: EventMsg) -> None:
        raise RuntimeError("Shouldn't be used")

    @abstractmethod
    def refresh(self) -> None:
        raise RuntimeError("Shouldn't be used")

    @abstractmethod
    def draw(self) -> None:
        raise RuntimeError("Shouldn't be used")

    @abstractmethod
    def resize(self, height, width) -> None:
        raise RuntimeError("Shouldn't be used")

    def _refresh(self) -> None:
        self.window.refresh()

    def _resize(self, height, width):
        self.height = height
        self.width = width

        self.window.resize(height, width)

class TimerTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height)

        self._text_effect = NoneTextEffect()
        self._figlet = Figlet(font="standard")
        self._logger = logging.getLogger(".timer_window")

        self._time = ""
        self._color = None
        self._on_break = False

    def resize(self, height, width):
        layout = main_layout(height,width)
        self._resize(layout["timer_height"], layout["timer_width"])
        self.draw()

    def draw(self):
        self.window.clear()
        if self._on_break:
            self._draw_on_break()
        else:
            self._draw_default_layout()

    def process(self, msg):
        match msg.kind:
            case Event.TimeChange:
                self._time = msg.msg

            case Event.TimerStopped:
                self._text_effect = BlinkTextEffect()

            case Event.AudioPlayback:
                self._text_effect = SlideTextEffect()

            case Event.AudioStopped | Event.TimerResumed | Event.PomodoroBegin:
                self._text_effect = NoneTextEffect()

            case Event.BreakBegin:
                self._start_color()
                self._on_break = True
                self.draw()

            case Event.BreakFinished:
                self._shutdown_color()
                self._on_break = False
                self.draw()

            case _:
                pass
        
    def refresh(self):
        if self._text_effect.empty():
            self._text_effect.refill()

        self._text_effect.render(self, self._spaced_str(self._time))

        self._refresh()

    def render(self, text):
        figlet_str = self._figlet.renderText(text)

        start_y = self.height // 3 + 2
        start_x = self.width // 3 + 7
        for index, line in enumerate(figlet_str.splitlines()):
            self.window.addstr( start_y + index, 1, " " * (self.width - 2))  # Limpiar la línea
            self.window.addstr( start_y + index, start_x, line.rstrip())

    def addstr(self, y, x, text):
        if curses.has_colors() and self._color:
            self.window.addstr(y,x,text,self._color)
        else:
            self.window.addstr(y,x,text)

    def erase(self):
        self.window.erase()

    def box(self):
        self.window.box()

    def _draw_on_break(self):
        self.window.box()
        self.addstr(0, 2, " En descanso ")

    def _draw_default_layout(self):
        self.window.box()
        self.addstr(0, 2, " Tiempo para finalizar ")

    def _start_color(self):
        self._color = curses.color_pair(1) # green color

    def _shutdown_color(self):
        self._color = None

    def _spaced_str(self, time_str):
        numbers_splited = time_str.split(":")
        return " : ".join(numbers_splited)

class AppMessagesTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height) 

        self._app_messages = []

    def resize(self, height, width):
        layout = main_layout(height,width)
        self._resize(layout["app_messages_height"], layout["app_messages_width"])
        self.draw()

    def draw(self):
        self.window.clear()
        self.window.box()
        self.window.addstr(0, 2, " Mensajes de la aplicación ")

    def process(self, msg) -> None:
        if msg.kind == Event.App:
            self._app_messages.append(msg.msg)

    def refresh(self):
        for index, msg in enumerate(list(reversed(self._app_messages))[:self.height-2]):
            self.window.addstr(index+1,1," " * (self.width - 2))  # Limpiar la línea
            self.window.addstr(index+1,1,self._shortened(msg))

        self._refresh()
    
    def _shortened(self, text):
        max_allowed = self.width - 3 - 3 # border offset is 3 and elipsis are also 3
        return text[:max_allowed] + "..." if len(text) > max_allowed else text

class CommandInputTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height) 

        self._command = ""

    def resize(self, height, width):
        layout = main_layout(height,width)
        self._resize(layout["command_input_height"], layout["command_input_width"])
        self.draw()

    def draw(self):
        self.window.clear()
        self.window.box()
        self.window.addstr(0, 2, " Comandos tipeados ")

    def process(self, msg):
        if msg.kind == Event.Cmd:
            self._command = msg.msg

    def refresh(self):
        self.window.addstr(1, 1, "Último comando presionado: {}".format(self._command))

        self._refresh()

class ManualTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window=window, width=width, height=height)

        self._manual = self._timer_manual()

    def resize(self, height, width):
        layout = main_layout(height,width)
        self._resize(layout["manual_height"], layout["manual_width"])
        self.draw()

    def draw(self):
        self.window.clear()
        self.window.box()
        self.window.addstr(0, 2, " Manual ")

    def process(self, msg):
        if msg.kind == Event.TimerInit:
            self._manual = self._timer_manual()
            self.window.clear()
            self.draw()
        elif msg.kind == Event.PomodoroInit:
            self._manual = self._pomodoro_manual()
            self.window.clear()
            self.draw()

    def refresh(self):
        for index, line in enumerate(list(filter(None,self._manual.splitlines()))):
            self.window.addstr(index+2, 1, line)

        self._refresh()

    def _timer_manual(self):
        manual = """
        Las opciones de teclas son:
        p   Pausar/continuar con el temporizador
        f   Finalizar el temporizador ó Detener el sonido de finalización del timer.
        t   Iniciar/detener un stopwatch
        i   Agregar una intención/propósito para la sesión en curso
        r   Cambiar el tag actual
        """
        return manual

    def _pomodoro_manual(self):
        manual = """
        Las opciones de teclas son:
        f   Finalizar el temporizador ó Detener el sonido de finalización del timer.
        t   Iniciar/detener un stopwatch
        i   Agregar una intención/propósito para la sesión en curso
        r   Cambiar el tag actual
        """
        return manual

class StatusBarTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height) 

        self._tag = ""
        self._purpose = ""
        self._end_time = ""
        self._pomodoros_done = 0 
        self._pomodoros_to_complete = "?"

        self._end_time_dirty = True
        self._SPACE_FOR_EACH = 30
        self._END_TIME_TITLE = "Hora de fin:"
        self._POMODOROS_TITLE = "Pomodoros:"
        self._TAG_TITLE = "tag:"
        self._PURPOSE_TITLE = "Intención:"

    def resize(self, height, width):
        layout = main_layout(height,width)
        self._resize(layout["status_bar_height"], layout["status_bar_width"])
        self.draw()

    def draw(self):
        self.window.clear()
        self.window.box()
        self.window.addstr(0, 2, " Status ")

    def process(self, msg) -> None:
        match msg.kind:
            case Event.TagChanged | Event.TagSetted:
                self._tag = msg.msg if msg.msg else ""
            
            case Event.PurposeAdded | Event.PurposeSetted:
                self._purpose = msg.msg

            case Event.TimerResumed | Event.TimerInitiated:
                self._end_time = msg.msg
                self._end_time_dirty = False

            case Event.TimerStopped:
                self._end_time_dirty = True

            case Event.PomodoroSetted:
                self._pomodoros_to_complete = str(msg.msg)

            case Event.PomodoroFinished:
                self._pomodoros_done += 1

    def refresh(self):
        pos_y = 1
        pos_x = 2

        # End time
        self.window.addstr(pos_y, pos_x, self._END_TIME_TITLE)
        action = lambda: self.window.addstr(pos_y, pos_x + len(self._END_TIME_TITLE) + 1, self._end_time)
        if self._end_time_dirty:
            self._with_effect(curses.A_DIM, action)
        else: 
            action()
        pos_x += self._SPACE_FOR_EACH
        
        # Pomodoros
        self.window.addstr(pos_y, pos_x, self._POMODOROS_TITLE)
        pomodoros_text = "{}/{}".format(self._pomodoros_done,self._pomodoros_to_complete)
        action = lambda: self.window.addstr(pos_y, pos_x + len(self._POMODOROS_TITLE) + 1, pomodoros_text)
        if str(self._pomodoros_done) == self._pomodoros_to_complete:
            self._with_effect(curses.A_BLINK,action)
        else:
            action()
        pos_x += self._SPACE_FOR_EACH

        # Tag
        self.window.addstr(pos_y, pos_x, self._TAG_TITLE)
        offset = len(self._TAG_TITLE) + 1
        action = lambda: self.window.addstr(pos_y, pos_x + offset, self._shortened(self._tag, pos_x, offset))
        self._with_effect(curses.A_STANDOUT, action)
        pos_x += self._SPACE_FOR_EACH
        
        # Purpose
        self.window.addstr(pos_y, pos_x, self._PURPOSE_TITLE)
        offset = len(self._PURPOSE_TITLE) + 1
        self.window.addstr(pos_y, pos_x + offset, self._shortened_last(self._purpose, pos_x, offset))
        pos_x += self._SPACE_FOR_EACH
        
        self._refresh()

    def _shortened(self, text, begin_pos_x, offset):
        """
        The text is shortened to be in the range for this section minus 1 unit 
        for correct spacing with the next title
        """
        return text[:self._SPACE_FOR_EACH - offset -1]

    def _shortened_last(self, text, begin_pos_x, offset):
        """
        The text is shortened to be in the range for this section minus 1 unit 
        for correct spacing with the next title
        """
        line_width = self.width - 2
        line_width_available = line_width - begin_pos_x - offset
        if len(text) > line_width_available - 3:
            text = text[:line_width_available - 3] + "..."

        return text

    def _with_effect(self, effect, action):
        self.window.attron(effect)

        action()

        self.window.attroff(effect)

class PurposeInputTile(Tile):
    def __init__(self, window, width , height):
        super().__init__(window,width,height)

        self._show = False

    def resize(self, height, width):
        layout = input_layout(height,width)
        self._resize(layout["win_height"], layout["win_width"])
        self.draw()

    def process(self, msg):
        if msg.kind == Event.AddPurpose:
            self._show = True

    def refresh(self):
        if self._show:
            msg = "¿Cuál es el objetivo de este pomodoro?"
            self.window.border()
            self.window.addstr(1, 2, msg)
            textbox_win = self.window.derwin(self.height-4, self.width-3, 2, 2)
            textbox = textpad.Textbox(textbox_win)
            self.window.refresh()

            def validator(ascii_key):
                ascii_enter = 10
                if ascii_key == ascii_enter: 
                    return curses.ascii.BEL
                return ascii_key
            purpose = textbox.edit( validator ).strip()

            textbox_win = None
            self._show = False
            event_purpose_added(_msg_queue, purpose)
            event_purpose_finished(_msg_queue)
            event_layout_draw(_msg_queue)
            self.window.clear()

    def draw(self):
        self.window.clear()

class TagInputTile(Tile):
    def __init__(self, window, width , height, tags):
        super().__init__(window,width,height)
        self.window.keypad(True)

        self._show = False

        self._no_tag = ">Sin tag<"
        tags.append(self._no_tag)
        self._tags = tags

    def resize(self, height, width):
        layout = tag_input_layout(height,width)
        self._resize(layout["win_height"], layout["win_width"])
        self.draw()

    def process(self, msg):
        if msg.kind == Event.TagChange:
            self._show = True

    def refresh(self):
        if self._show:
            selected = self._show_list_menu()

            self._show = False
            tag = self._tags[selected] if self._tags[selected] != self._no_tag else None
            event_tag_changed(_msg_queue, tag)
            event_tag_finished(_msg_queue)
            event_layout_draw(_msg_queue)

    def draw(self):
        self.window.clear()
        self.window.border()
        self.window.addstr(0, 2, " ¿A qué tag querés cambiar? ")

    def _show_list_menu(self):
        menu_items = self._tags
        selected_idx = 0
        self.draw()
        h = self.height
        w = self.width

        while True:
            # Mostrar opciones y resaltar la seleccionada
            for i, item in enumerate(menu_items):
                x = w // 2 - len(item) // 2
                y = h // 2 - len(menu_items) // 2 + i

                if i == selected_idx:
                    self.window.attron(curses.A_REVERSE)  # Resalta la opción
                    self.window.addstr(y, x, item)
                    self.window.attroff(curses.A_REVERSE)
                else:
                    self.window.addstr(y, x, item)

            self.window.refresh()

            # Capturar entrada del usuario
            key = self.window.getch()

            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(menu_items) - 1:
                selected_idx += 1
            elif key == ord("\n"):  # Enter para seleccionar
                break

        self.window.clear()
        return selected_idx

class TextEffect(ABC):
    @abstractmethod
    def empty(self) -> bool:
        pass

    @abstractmethod
    def refill(self) -> None:
        pass

    @abstractmethod
    def render(self, window, text) -> None:
        pass

class NoneTextEffect(TextEffect):
    def __init__(self):
        self._logger = logging.getLogger(".none_text_effect")

    def empty(self):
        return False

    def refill(self):
        pass

    def render(self, window, text):
        window.render(text)

class SlideTextEffect(TextEffect):
    def __init__(self):
        self._logger = logging.getLogger(".slide_text_effect")
        self._fill()
        self._position_to_affect = 0

    def empty(self):
        return self._period == []

    def refill(self):
        self._fill()

    def render(self, window, text):
        frame = self._frame()
        if frame:
            window.render(self._slide_effect(text))
        else:
            window.render(text)

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

    def render(self, window, text):
        frame = self._frame()
        if frame:
            window.render(text)
        else:
            window.erase()
            window.box()
            window.addstr(0, 2, " Tiempo para finalizar ")

    def _frame(self):
        return self._period.pop()

    def _fill(self):
        self._period = [False,True]
