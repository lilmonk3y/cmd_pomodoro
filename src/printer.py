from abc import abstractmethod, ABC
from pyfiglet import Figlet
import curses
from curses import textpad
from datetime import datetime, timedelta
import logging
from os import getpid
import signal
import subprocess

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
        TimerLayout(
            curses.newwin(height, width), 
            height, 
            width),
        build_input_layout(height,width),
        build_tag_input_layout(height,width,tags),
        screen=stdscr
     )).run()


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
        self._must_draw = True
        self._screen = screen

        self._msgs_pipe = _msg_queue.suscribe(*[event for event in Event],suscriber=getpid())
        signal.signal(signal.SIGWINCH, self._resize_event_handler)
        self._logger = logging.getLogger(".printer")

    def run(self):
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
                self._must_draw = True

            for layout in self._layouts:
                layout.process(msg)

    def _refresh_if_have_to(self):
        if not self._time_is_up():
            return
        
        for layout in self._layouts:
            if self._must_draw:
                layout.draw()

            layout.refresh()
            
        self._must_draw = False
        self._set_next_update()

    def _time_is_up(self):
        return self._must_update < datetime.now()

    def _set_next_update(self):
        self._must_update = datetime.now() + timedelta(seconds=0.5)

    def _resize_event_handler(self, signum, frame):
        height, width = self._native_getmaxyx()
        curses.resize_term(height,width)
        curses.resizeterm(height, width)

        self._screen.clear()
        for layout in self._layouts:
            layout.resize(height, width)

        self._must_draw = True

    def _native_getmaxyx(self):
        def get_os_cmd_output(cmd_list):
            return int(subprocess.run(cmd_list, stdout=subprocess.PIPE).stdout.decode('utf-8'))
        
        return get_os_cmd_output(['tput','lines']), get_os_cmd_output(['tput','cols'])

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

class TimerLayout(Layout):
    def __init__(self, window, height, width): 
        self._window = window
        self._height = height
        self._width = width

        layout = self.main_layout()

        self._status_bar = StatusBarTile(
            window=self._window.derwin(
                layout["status_bar_y"], 
                layout["status_bar_x"], 
                layout["status_bar_y_offset"], 
                layout["status_bar_x_offset"]), 
            width=layout["status_bar_x"],
            height=layout["status_bar_y"])

        self._timer = TimerTile(
            window=self._window.derwin(
                layout["timer_y"], 
                layout["timer_x"], 
                layout["timer_y_offset"], 
                layout["timer_x_offset"]), 
            width=layout["timer_x"],
            height=layout["timer_y"])

        assert layout["manual_y"] + layout["manual_y_offset"] < self._height, "height out of range"
        assert layout["manual_x"] + layout["manual_x_offset"] < self._width, "width out of range"
        self._manual = ManualTile(
            window=self._window.derwin(
                layout["manual_y"], 
                layout["manual_x"], 
                layout["manual_y_offset"], 
                layout["manual_x_offset"]), 
            width=layout["manual_x"],
            height=layout["manual_y"])

        self._command_input = CommandInputTile(
            window=self._window.derwin(
                layout["command_input_y"], 
                layout["command_input_x"], 
                layout["command_input_y_offset"], 
                layout["command_input_x_offset"]), 
            width=layout["command_input_x"],
            height=layout["command_input_y"])

        self._app_messages = AppMessagesTile(
            window=self._window.derwin(
                layout["app_messages_y"], 
                layout["app_messages_x"], 
                layout["app_messages_y_offset"], 
                layout["app_messages_x_offset"]), 
            width=layout["app_messages_x"],
            height=layout["app_messages_y"])

        self._tiles = [
            self._status_bar,
            self._timer,
            self._manual,
            self._command_input,
            self._app_messages
        ]

    def resize(self, height, width):
        self._height = height
        self._width = width

        layout = self.main_layout()

        self._status_bar.resize(
            layout["status_bar_y"], layout["status_bar_x"], 
            0, 0)
        self._timer.resize(
            layout["timer_y"], layout["timer_x"], 
            layout["timer_y_offset"], layout["timer_x_offset"])
        self._manual.resize(
            layout["manual_y"], layout["manual_x"], 
            layout["manual_y_offset"], layout["manual_x_offset"])
        self._command_input.resize(
            layout["command_input_y"], layout["command_input_x"], 
            layout["command_input_y_offset"], layout["command_input_x_offset"])
        self._app_messages.resize(
            layout["app_messages_y"], layout["app_messages_x"], 
            layout["app_messages_y_offset"], layout["app_messages_x_offset"])

    def main_layout(self):
        height = self._height
        width = self._width

        status_bar_height = 3
        timer_height = (height // 2 - status_bar_height)
        command_input_height = 3

        manual_height = (height // 2)
        manual_width = (width // 2)

        height_offset = timer_height + status_bar_height

        return dict({
            "status_bar_y" : status_bar_height,
            "status_bar_x" : width,
            "status_bar_y_offset" : 0,
            "status_bar_x_offset" : 0,

            "timer_y": timer_height,
            "timer_x" : width,
            "timer_y_offset" : status_bar_height,
            "timer_x_offset" : 0,

            "manual_y" : manual_height,
            "manual_x" : manual_width,
            "manual_y_offset" : height_offset,
            "manual_x_offset" : 0,

            "command_input_y" : command_input_height,
            "command_input_x" : manual_width,
            "command_input_y_offset" : height_offset,
            "command_input_x_offset" : manual_width,

            "app_messages_y" : (height//2 - command_input_height),
            "app_messages_x" : manual_width,
            "app_messages_y_offset" : (height_offset + command_input_height),
            "app_messages_x_offset" : manual_width
        })

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

    def resize(self, height, width, height_offset=0, width_offset=0):
        self.height = height
        self.width = width

        self.window.clear()
        self.window.resize(height, width)

        if height_offset != 0 and width_offset != 0:
            self.window.mvderwin(height_offset, width_offset)

    def _refresh(self) -> None:
        self.window.refresh()

    def addstr(self, pos_y, pos_x, text, color=None):
        in_range = pos_y < self.height and pos_x < self.width
        if not in_range:
            return 

        limit = self.width -2 -pos_x
        if color:
            self.window.addstr(pos_y, pos_x, text[:limit], color)
        else:
            self.window.addstr(pos_y, pos_x, text[:limit])

class TimerTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height)

        self._text_effect = NoneTextEffect()
        self._figlet = Figlet(font="standard")
        self._logger = logging.getLogger(".timer_window")

        self._time = ""
        self._color = None
        self._on_break = False
        self._start_y = 1
        self._start_x = 1
        self._ticks = 0

    def resize(self, height, width, height_offset, width_offset):
        super().resize(height, width, height_offset, width_offset)

        # force time placement update
        self._start_y = 1
        self._start_x = 1
        self._ticks = 0

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
                self._ticks += 1

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
        splited_str = figlet_str.splitlines()
        self._update_once_when_str_fullsize(splited_str)
        for index, line in enumerate(splited_str):
            self.addstr( self._start_y + index, 1, " " * (self.width - 2))  # Limpiar la línea
            self.addstr( self._start_y + index, self._start_x, line.rstrip())

    def addstr(self, pos_y, pos_x, text):
        if curses.has_colors() and self._color:
            super().addstr(pos_y,pos_x,text,self._color)
        else:
            super().addstr(pos_y,pos_x,text)

    def erase(self):
        self.window.erase()

    def box(self):
        self.window.box()

    def _update_once_when_str_fullsize(self, figlet_matrix):
        true_after_first_update = self._start_x > 1 and self._start_y > 1 and self._ticks > 2
        if true_after_first_update:
            return

        str_height = len(figlet_matrix)
        one_line_width = len(figlet_matrix[0]) if str_height > 0 else 0
        self._start_y = self.height // 2 - str_height // 2
        self._start_x = self.width // 2 - one_line_width // 2

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

    def draw(self):
        self.window.clear()
        self.window.box()
        self.addstr(0, 2, " Mensajes de la aplicación ")

    def process(self, msg) -> None:
        if msg.kind == Event.App:
            self._app_messages.append(msg.msg)

    def refresh(self):
        for index, msg in enumerate(list(reversed(self._app_messages))[:self.height-2]):
            self.addstr(index+1,1," " * (self.width - 2))  # Limpiar la línea
            self.addstr(index+1,1,self._shortened(msg))

        self._refresh()
    
    def _shortened(self, text):
        max_allowed = self.width - 3 - 3 # border offset is 3 and elipsis are also 3
        return text[:max_allowed] + "..." if len(text) > max_allowed else text

class CommandInputTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window, width, height) 

        self._command = ""

    def draw(self):
        self.window.clear()
        self.window.box()
        self.addstr(0, 2, " Comandos tipeados ")

    def process(self, msg):
        if msg.kind == Event.Cmd:
            self._command = msg.msg

    def refresh(self):
        self.addstr(1, 1, "Último comando presionado: {}".format(self._command))

        self._refresh()

class ManualTile(Tile):
    def __init__(self, window, width, height):
        super().__init__(window=window, width=width, height=height)

        self._manual = self._timer_manual()

    def draw(self):
        self.window.clear()
        self.window.box()
        self.addstr(0, 2, " Manual ")

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
            self.addstr(index+2, 1, line)

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

    def draw(self):
        self.window.clear()
        self.window.box()
        self.addstr(0, 2, " Status ")

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
        self.addstr(pos_y, pos_x, self._END_TIME_TITLE)
        action = lambda: self.addstr(pos_y, pos_x + len(self._END_TIME_TITLE) + 1, self._end_time)
        if self._end_time_dirty:
            self._with_effect(curses.A_DIM, action)
        else: 
            action()
        pos_x += self._SPACE_FOR_EACH
        
        # Pomodoros
        self.addstr(pos_y, pos_x, self._POMODOROS_TITLE)
        pomodoros_text = "{}/{}".format(self._pomodoros_done,self._pomodoros_to_complete)
        action = lambda: self.addstr(pos_y, pos_x + len(self._POMODOROS_TITLE) + 1, pomodoros_text)
        if str(self._pomodoros_done) == self._pomodoros_to_complete:
            self._with_effect(curses.A_BLINK,action)
        else:
            action()
        pos_x += self._SPACE_FOR_EACH

        # Tag
        self.addstr(pos_y, pos_x, self._TAG_TITLE)
        offset = len(self._TAG_TITLE) + 1
        action = lambda: self.addstr(pos_y, pos_x + offset, self._shortened(self._tag, pos_x, offset))
        self._with_effect(curses.A_STANDOUT, action)
        pos_x += self._SPACE_FOR_EACH
        
        # Purpose
        self.addstr(pos_y, pos_x, self._PURPOSE_TITLE)
        offset = len(self._PURPOSE_TITLE) + 1
        self.addstr(pos_y, pos_x + offset, self._shortened_last(self._purpose, pos_x, offset))
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

    def process(self, msg):
        if msg.kind == Event.AddPurpose:
            self._show = True

    def refresh(self):
        if self._show:
            textbox_win = self.window.derwin(self.height-4, self.width-3, 2, 2)
            textbox = textpad.Textbox(textbox_win)
            self.draw()
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

    def draw(self):
        self.window.clear()
        self.window.border()
        self.addstr(1, 2,  "¿Cuál es el objetivo de este pomodoro?")

class TagInputTile(Tile):
    def __init__(self, window, width , height, tags):
        super().__init__(window,width,height)
        self.window.keypad(True)

        self._show = False

        self._no_tag = ">Sin tag<"
        tags.append(self._no_tag)
        self._tags = tags

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
        self.addstr(0, 2, " ¿A qué tag querés cambiar? ")

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
                    self.addstr(y, x, item)
                    self.window.attroff(curses.A_REVERSE)
                else:
                    self.addstr(y, x, item)

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
