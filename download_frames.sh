#!/usr/bin/env bash

VIDEO=bad-apple.webm
FRAMERATE=30
WIDTH=48
HEIGHT=36

if test -f "$VIDEO"; then
    echo "$VIDEO already exists, skipping download"
else
    yt-dlp 'https://www.youtube.com/watch?v=FtutLA63Cp8' -o $VIDEO
fi

rm -rf frames
mkdir -p frames
ffmpeg -i $VIDEO -vf "scale=$WIDTH:$HEIGHT" -r $FRAMERATE/1 'frames/%04d.bmp'
