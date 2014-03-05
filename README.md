##pokr
======

An OCR script for the TwitchPlaysPokemon stream.

##Installation:
####Mac
1. ```$ brew install ffmpeg```
1. ```$ brew tap homebrew/science```
1. ```$ brew install opencv --with-ffmpeg```

####Debian/Ubuntu
1. ```$ sudo apt-get install python-opencv```

####Common
1. ```pip install -r ./requirements.txt```

##Usage
```ocr.py [--show] [-f FILENAME]```: runs, displaying current status on stdout and dumping frames to frames.log

Pokr can also be used as a module:

    import pokr

    def printer(data):
        print data['text']

    proc = pokr.StreamProcessor()
    proc.add_handler(printer)
    proc.run()

Handlers receive a dict with 'text' as a string of the recognized characters, and 'frame' as the
current image from the stream.
