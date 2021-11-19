#!/bin/bash

echo "starting counter"
sleep 1
gnome-terminal --window --working-directory=/home/jetson/pillcounter --command ./startCounter.sh

exit 0
