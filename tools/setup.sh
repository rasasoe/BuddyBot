#!/bin/bash
# Setup script for BuddyBot

echo "Setting up BuddyBot..."

# Install ROS 2 Jazzy
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt upgrade -y
sudo apt install -y ros-jazzy-desktop

# Source ROS 2
source /opt/ros/jazzy/setup.bash

# Install dependencies
sudo apt install -y python3-colcon-common-extensions python3-rosdep
sudo rosdep init
rosdep update

# Install additional packages
sudo apt install -y python3-cv-bridge python3-pyaudio
pip3 install --quiet --break-system-packages SpeechRecognition 2>/dev/null || pip3 install --quiet SpeechRecognition

# For Pico
# Assume Thonny or mpremote for flashing

echo "Setup complete. Remember to flash pico/main.py to the Pico."
