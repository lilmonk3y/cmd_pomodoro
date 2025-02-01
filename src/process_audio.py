import pydub, simpleaudio, wave
import time
import os
from datetime import datetime, timedelta

from utils import path_to_file, file_path_in_home
from global_data import TEMPORARY_PATH
from messages import *

def audio_process(args, audio_path, msg_queue):
    """audio - play audio on background"""

    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = file_path_in_home(TEMPORARY_PATH, "timer_audio.wav")
    pipe = msg_queue.suscribe(Event.AudioTerminate, suscriber=os.getpid())

    try:
        audio.export(NEW_AUDIO_PATH, format="wav")
        wave_object = simpleaudio.WaveObject.from_wave_file(NEW_AUDIO_PATH)
        play_object = wave_object.play()

        continue_play = when_to_stop(NEW_AUDIO_PATH)
        # and play_object.is_playing()
        while continue_play() :
            if pipe.poll():
                msg = pipe.recv()

                if msg.kind == Event.AudioTerminate:
                    play_object.stop()
                    break

            else:
                time.sleep(0.5)

        event_audio_ended(msg_queue)

    finally:
        if os.path.exists(NEW_AUDIO_PATH):
            os.remove(NEW_AUDIO_PATH)

        msg_queue.unsuscribe(os.getpid(), [Event.AudioTerminate])

def when_to_stop(wav_file):
    length = length_in_seconds(wav_file)
    end_of_song = datetime.now() + timedelta(seconds=(length-1))
    return lambda: datetime.now() < end_of_song

def length_in_seconds(file):
    length = None
    with wave.open(file, 'rb') as wav:
        length = wav.getnframes() / float(wav.getframerate())
    return int(length)

def audio_process_short(args, audio_path, msg_queue):
    mp3_path = path_to_file(audio_path)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    NEW_AUDIO_PATH = file_path_in_home(TEMPORARY_PATH, "pomo_audio.wav")

    try:
        audio.export(NEW_AUDIO_PATH, format="wav")
        wave_object = simpleaudio.WaveObject.from_wave_file(NEW_AUDIO_PATH)
        play_object = wave_object.play()
        time.sleep(length_in_seconds(NEW_AUDIO_PATH))

    finally:
        event_audio_stopped(msg_queue)
        if os.path.exists(NEW_AUDIO_PATH):
            os.remove(NEW_AUDIO_PATH)
