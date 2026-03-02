#!/bin/bash
cd /mt5docker

# remove display lock if any
rm -rf /tmp/.X100-lock

echo "Starting MetaTrader 5 in headless mode..."

# set up display
export DISPLAY=:100
# Xvfb :100 -ac -screen 0 1024x768x24 &
Xvfb :100 -ac -screen 0 1x1x8 &


if [ ! -d "/opt/wineprefix/drive_c/Program Files/meta101" ]; then
  unzip /mt5docker/meta.zip -d '/opt/wineprefix/drive_c/Program Files' && \
  mv "/opt/wineprefix/drive_c/Program Files/meta" "/opt/wineprefix/drive_c/Program Files/MetaTrader 5"
  rm -f "/opt/wineprefix/drive_c/Program Files/MetaTrader 5/Config/servers.dat" && \
  cp /volumes/servers.dat "/opt/wineprefix/drive_c/Program Files/MetaTrader 5/Config/servers.dat" && \
  rm -f "/opt/wineprefix/drive_c/Program Files/MetaTrader 5/Config/common.ini" && \
  cp /volumes/common.ini "/opt/wineprefix/drive_c/Program Files/MetaTrader 5/Config/common.ini"

  mv "/opt/wineprefix/drive_c/Program Files/MetaTrader 5" "/opt/wineprefix/drive_c/Program Files/meta"
  cp -r "/opt/wineprefix/drive_c/Program Files/meta" "/opt/wineprefix/drive_c/Program Files/meta101"
fi

sleep 1

wine python /mt5docker/script.py

# prevent container termination
while true
do
  sleep 1
done