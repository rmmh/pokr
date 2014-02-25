#!/bin/bash
#tput civis
livestreamer twitch.tv/twitchplayspokemon source -O | ./ocr.py $@