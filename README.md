# Instalarlo

Tenes que estar en un sistema Linux, ya que en otros sistemas el programa no anda por el momento.

```bash
# Te traes el instalador del programa en la versión del mismo que prefieras
curl -o install.sh https://raw.githubusercontent.com/lilmonk3y/cmd_pomodoro/refs/tags/v0.11.0/install.sh

# Le das permisos para ejecutar y lo ejecutas con el argumento 'install' y la versión que más te guste
chmod +x install.sh 
./install.sh install v0.11.0

# Una vez instalado agregas el alias del programa a tu '.bashrc' o '.zshrc' y ya podés invocar al programa por su nombre
cmd_pomodoro --help
```

# Configurarlo

El programa necesita que le configuremos una serie de valores que usará para la ejecución. Entre ellos está la duración de los pomodoros y los archivos de audio que usará para cuando termine el temporizador o entre cada pomodoro.

```bash
cmd_pomodoro config -pomodoro_time 30 -finish_audio "Scripts/temporizador_logger/audio/JAAA.mp3" -intermediate_audio "Scripts/temporizador_logger/audio/notification_sound_1.mp3" -log_file "Dropbox/obsidian_sync/obsidian_dropbox/logging/pomodoro_log.md"
```

Además se lo puede configurar, y luego invocar con un argumento opcional para indicar que está configurado en modo de testing.

```bash
cmd_pomodoro --test config -pomodoro_time 1 -finish_audio "Scripts/temporizador_logger/audio/JAAA.mp3" -intermediate_audio "Scripts/temporizador_logger/audio/notification_sound_1.mp3" -log_file "Scripts/temporizador_logger/test_log.md"
```

# Ejecutarlo

El comando del programa es **timer** y con él iniciamos un período de concentración. El mismo toma una duración en minutos y opcionalmente le podemos decir en que vamos a dedicar dicho tiempo.

```bash
cmd_pomodoro timer 60 -t programar
```

# Desinstalarlo

Si encontraste un error o te cansaste del programa podes desinstalarlo con un desinstalador. **Importante: Todos los archivos del programa, como sus configuraciones, se van a perder.

```bash
./install.sh uninstall
```

# Comandos útiles mientras desarrolas en mejoras

Entrar y salir a un entorno de Python

```bash
# Entrar en el venv
source pyenv/bin/activate 

# Salir
deactivate
```

