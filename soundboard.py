#!/usr/bin/env python
# pylint: disable=E0611

import argparse
import json
import pyaudio
import wave
import sys
import os
import math
import time
import keyboard
import threading

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication, QMenuBar, QMainWindow, QAction, QGridLayout, QWidget, QPushButton, QFileDialog, QLabel, QMenu, QInputDialog
import qtawesome as qta

ARG_PARSER = argparse.ArgumentParser(description='Plays sounds my dude')
ARG_PARSER.add_argument('-list', help='Show input and output devices')
ARG_PARSER.add_argument(
    '-soundmap', '-sm', help='The configuration for the user\'s sounds', default='sound_map.json')

PROGRAM_ARGS = ARG_PARSER.parse_args()

OUTPUT_DEVICES = {}


class Sound(object):
    def __init__(self, title, file_name):
        self.title = title
        self.file_name = file_name
        self.shortcut = ''


class SoundWidget(QWidget):
    def __init__(self, sound):
        super().__init__()
        self.sound = sound
        self.channel = -1
        self.playing = False
        self.muted = False
        grid_layout = QGridLayout(self)

        play_button = QPushButton('Play!')
        play_button.setObjectName('playbutton')
        play_button.clicked.connect(self._play_sound())
        label = QLabel(self.sound['title'])
        label.setObjectName('title')
        label.setAlignment(Qt.AlignCenter)

        title_position = (0, 0)
        button_pos = (1, 0)
        grid_layout.addWidget(label, *title_position)
        grid_layout.addWidget(play_button, *button_pos)
        self.setLayout(grid_layout)

    def _play_sound(self):
        def start_audio():
            if self.channel != -1 and not self.playing:
                thread = threading.Thread(target=self.play)
                thread.setDaemon(True)
                thread.start()
        return start_audio

    def play(self):
        sound_file = wave.open('sounds/%s.wav' % self.sound['file_name'], 'rb')

        audio = pyaudio.PyAudio()
        stream = audio.open(format=audio.get_format_from_width(sound_file.getsampwidth()),
                            channels=sound_file.getnchannels(), rate=sound_file.getframerate(),
                            output=True, output_device_index=self.channel)

        data = sound_file.readframes(1024)


        self.playing = True

        while data and self.playing:
            if not self.muted:
                stream.write(data)
            else:
                stream.write(b'0' * 1024)
            data = sound_file.readframes(1024)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        self.playing = False

    def set_channel(self, channel):
        self.channel = channel

    # def minimumSizeHint(self):
    #     height = (self.findChild(QPushButton, 'playbutton').minimumSizeHint().height() +
    #                  self.findChild(QLabel, 'title').minimumSizeHint().height() + 20)

    #     width = (self.findChild(QPushButton, 'playbutton').minimumSizeHint().width()
    #                  + self.findChild(QLabel, 'title').minimumSizeHint().width() + 20)
    #     return QSize(width, height)


class SoundboardGrid(QWidget):
    def __init__(self, sounds, channel):
        super().__init__()
        self.channel = channel
        self.sounds = sounds
        self.widgets = []
        layout = QGridLayout(self)
        positions = [(i, j) for i in range(math.ceil(len(sounds) / 6))
                     for j in range(6)]
        if self.sounds:
            for position, sound in zip(positions, sounds):
                sound_widget = SoundWidget(sound)
                sound_widget.setParent(self)
                layout.addWidget(sound_widget, *position)
                self.widgets.append(sound_widget)

        self.setLayout(layout)

        max_width = 0
        for child in self.findChildren(SoundWidget):
            max_width = max(child.sizeHint().width(), max_width)

        for child in self.findChildren(SoundWidget):
            child.setMinimumWidth(max_width)

    def add_sound(self, sound):
        count = self.layout().count()
        sound_widget = SoundWidget(sound)
        sound_widget.set_channel(self.channel)
        position = (math.floor(count / 6), count % 6)
        self.layout().addWidget(sound_widget, *position)

    def set_channel(self, channel):
        self.channel = channel
        for widget in self.findChildren(SoundWidget):
            widget.channel = channel

    def toggle_mute(self):
        for widget in self.findChildren(SoundWidget):
            widget.muted = not widget.muted


class Soundboard(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config_name = config
        self.config = self._load_config(config)
        self.sounds = self.config['sounds']
        self.page = 0
        self._init_show()

    def _load_config(self, config):
        if os.path.isfile(config):
            with open(config, 'r') as config_file:
                return json.loads(''.join(config_file.readlines()))
        else:
            with open(config, 'w') as config_file:
                config_file.write(json.dumps({'sounds': [], 'out_device': -1}))
            return {'sounds': [], 'out_device': -1}

    def _init_show(self):
        self.grid = SoundboardGrid(self.sounds, self.config['out_device'])
        self.grid.set_channel(self.config['out_device'])
        self.grid.setParent(self)
        self.setCentralWidget(self.grid)
        self.setWindowTitle('Sound Board')
        self.setGeometry(300, 300, 350, self.sizeHint().height())
        self.setWindowTitle('Sound Board')
        self.setWindowIcon(qta.icon('fa.headphones'))
        menu_bar = QMenuBar()

        file_menu = menu_bar.addMenu('&File')
        add_sound = QAction('Add Sound', self)
        add_sound.triggered.connect(self._add_sound)
        file_menu.addAction(add_sound)

        sound_menu = menu_bar.addMenu('Sound')
        mute_sounds = QAction('Mute', self)
        mute_sounds.setCheckable(True)
        mute_sounds.setShortcut('Ctrl+m')
        mute_sounds.triggered.connect(self.grid.toggle_mute)
        sound_menu.addAction(mute_sounds)

        output_menu = menu_bar.addMenu('Output Device')
        output_menu.setObjectName('outdevices')
        for device in OUTPUT_DEVICES:
            select_device = QAction(device, output_menu)
            select_device.setCheckable(True)
            if self.config['out_device'] == OUTPUT_DEVICES[device]:
                select_device.setChecked(True)
            select_device.triggered.connect(self._set_output_device(select_device))
            output_menu.addAction(select_device)

        self.setMenuBar(menu_bar)
        self.show()

    def _add_sound(self):
        sound_file = QFileDialog.getOpenFileName()
        if sound_file[0] != '':
            title = QInputDialog.getText(self, 'Sound Name', 'Enter the name of the sound:')
            if sound_file[0].endswith('.wav'):
                if os.path.abspath(os.path.join('sounds', os.path.basename(sound_file[0]))) != os.path.abspath(sound_file[0]):
                    with open(os.path.join('sounds', os.path.basename(sound_file[0])), 'w') as output_file:
                        with open(os.path.abspath(sound_file[0]), 'r') as input_file:
                            output_file.writelines(input_file.readlines())

                sound = Sound(title[0], '.'.join(os.path.basename(sound_file[0]).split('.')[0:-1]))
                self.grid.add_sound(sound.__dict__)
                self.config['sounds'].append(sound.__dict__)
                self._save_config()

    def _set_output_device(self, name):
        def set_device():
            menu = self.menuBar().findChild(QMenu, 'outdevices')
            for action in menu.findChildren(QAction):
                if action.text() != name.text():
                    action.setChecked(False)
                else:
                    action.setChecked(True)
            self.grid.set_channel(OUTPUT_DEVICES[name.text()])
            self.config['out_device'] = OUTPUT_DEVICES[name.text()]
            self._save_config()
        return set_device

    def _save_config(self):
        with open(self.config_name, 'w') as config_file:
            config_file.write(json.dumps(self.config, indent='  '))


def main():
    # if PROGRAM_ARGS.list:
    #
    #     p.terminate()
    # for key in SOUND_MAP:
    #     temp = SOUND_MAP[key]
    #     keyboard.add_hotkey(key, play_audio, args=(temp,))
    #     keyboard.add_hotkey(key+'+u', play_audio, args=(temp,))
    # keyboard.wait()
    app = QApplication(sys.argv)
    sb = Soundboard(PROGRAM_ARGS.soundmap)
    sys.exit(app.exec_())


def load_output_devices():
    audio = pyaudio.PyAudio()
    info = audio.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (audio.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
            OUTPUT_DEVICES[audio.get_device_info_by_host_api_device_index(
                0, i).get('name')] = i


if __name__ == '__main__':
    load_output_devices()
    main()
