#!/bin/bash

INSTALLATION_PATH="/opt/cmd_pomodoro"
CONFIGURATION_PATH="~/.config/cmd_pomodoro"
TEMPORARY_PATH="~/.cache/cmd_pomodoro"
DATA_PATH="~/.local/share/cmd_pomodoro"
REPO="https://github.com/lilmonk3y/cmd_pomodoro.git"

install(){
	os=$( getOs )
	echo "Running on system named: $os"

  sudo mkdir -p ${INSTALLATION_PATH} &&
  mkdir -p ${CONFIGURATION_PATH} &&
  mkdir -p ${TEMPORARY_PATH} &&
  mkdir -p ${DATA_PATH}
  
  if [ $? -eq 0 ]; then
    echo "Directories created ✅"
  fi

  #latest_tag=$(git describe --tags `git rev-list --tags --max-count=1`)
  #git clone --branch ${latest_tag} ${REPO} ${TEMPORARY_PATH} 

  cd ${TEMPORARY_PATH}

  expected_tag=$1
  git -c advice.detachedHead=false clone -q --branch ${expected_tag} ${REPO} . 

  if [ $? -eq 0 ]; then
    echo "Repository cloned ✅"
  fi

  	sudo cp -r . ${INSTALLATION_PATH} &&
	rm -Rf ./\~/ # cleanup

  cd ${INSTALLATION_PATH}

  sudo rm -rf .git 

  sudo chmod +x src/temporizador_logger.py

  user=$(whoami)
  sudo chown -R ${user} ${INSTALLATION_PATH}

  echo "Installing dependencies 💪"
  echo ""
	echo "Installing pre-dependencies"
	echo ""
	
	if [[ $os -eq "Mac" ]]; then
		brew install cmake pkg-config cairo libffi pyenv
	elif [[ $os -eq "Linux" ]]; then
		apt-get install cmake pkg-config cairo libffi libffi-dev
	fi	

	# Set up pyenv
	pyenv install 3.10
	pyenv local 3.10
	export PYENV_ROOT="$HOME/.pyenv"
	[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
	eval "$(pyenv init - zsh)"	

	export PKG_CONFIG_PATH="/usr/local/opt/libffi/lib/pkgconfig"
	#CFLAGS=$(pkg-config --cflags libffi) LDFLAGS=$(pkg-config --libs libffi) 

	echo "End pre-dependencies"

	echo "Creating a virtual env on python version $( python --version )"
  sudo python -m venv venv && 
	sudo chown -R ${user} venv &&
	source venv/bin/activate && 
	sudo chmod +x /opt/cmd_pomodoro/venv/bin/python3 &&
	/opt/cmd_pomodoro/venv/bin/python3 -m ensurepip --upgrade &&
  	# /opt/cmd_pomodoro/venv/bin/python3 -m pip install gobject && 
  	/opt/cmd_pomodoro/venv/bin/python3 -m pip install -r requirements.txt && 
  deactivate

  if [ $? -eq 0 ]; then
    echo ""
    echo "Python venv environment created with all the dependencies ✅"
    echo "Application ready to be used 🙌"
  fi

  echo ""
  echo "add next line to ~/.zshrc"
  echo "alias cmd_pomodoro='${INSTALLATION_PATH}/src/temporizador_logger.py'"
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

getOs(){
	unameOut="$(uname -s)"
	case "${unameOut}" in
	    Linux*)     machine=Linux;;
	    Darwin*)    machine=Mac;;
	    CYGWIN*)    machine=Cygwin;;
	    MINGW*)     machine=MinGw;;
	    MSYS_NT*)   machine=MSys;;
	    *)          machine="UNKNOWN:${unameOut}"
	esac
	echo ${machine}
}

# run function from argument. It must be: install tag or uninstall
"$@"
