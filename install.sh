#!/bin/bash

INSTALLATION_PATH="/opt/cmd_pomodoro"
CONFIGURATION_PATH="/etc/opt/cmd_pomodoro"
TEMPORARY_PATH="/tmp/cmd_pomodoro"
DATA_PATH="/usr/share/cmd_pomodoro"
REPO="https://github.com/lilmonk3y/cmd_pomodoro.git"
latest_tag="v0.8.0"

install(){
  mkdir -p ${INSTALLATION_PATH} &&
  mkdir -p ${CONFIGURATION_PATH} &&
  mkdir -p ${TEMPORARY_PATH} &&
  mkdir -p ${DATA_PATH}
  
  if [ $? -eq 0 ]; then
    echo "Directories created ✅"
  fi

  #latest_tag=$(git describe --tags `git rev-list --tags --max-count=1`)
  #git clone --branch ${latest_tag} ${REPO} ${TEMPORARY_PATH} 

  cd ${TEMPORARY_PATH}

  git -c advice.detachedHead=false clone -q --branch ${latest_tag} ${REPO} . 

  if [ $? -eq 0 ]; then
    echo "Repository cloned ✅"
  fi

  cp -r . ${INSTALLATION_PATH}

  cd ${INSTALLATION_PATH}

  rm -rf .git 

  chmod +x temporizador_logger.py

  echo "Installing dependencies 💪"
  echo ""

  python3 -m venv pyenv && source pyenv/bin/activate && pip3 install -r requirements.txt && deactivate

  if [ $? -eq 0 ]; then
    echo ""
    echo "Python venv environment created with all the dependencies ✅"
    echo "Application ready to be used 🙌"
  fi

  echo ""
  echo "add next line to ~/.zshrc"
  echo "alias cmd_pomodoro='${INSTALLATION_PATH}/temporizador_logger.py'"
}

uninstall(){
  rm -rf ${INSTALLATION_PATH} &&
  rm -rf ${CONFIGURATION_PATH} &&
  rm -rf ${TEMPORARY_PATH} &&
  rm -rf ${DATA_PATH}

  if [ $? -eq 0 ]; then
    echo "App successfully deleted ✅"
    echo ""
  fi
  
  echo "run next command. Also delete the alias line from ~/.zshrc"
  echo "unalias cmd_pomodoro"
}

# run function from argument. It must be: install or uninstall
"$@"
