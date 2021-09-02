#!/bin/bash

/etc/init.d/dbus start
su signal -c "signal-cli --config /signal-data -u $1 --output=json daemon --system &"
#sleep 4;
su signal -c "python3 ./bot.py"
#su signal -c bash
#bash
