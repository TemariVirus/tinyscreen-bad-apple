#!/usr/bin/env bash

FRAMERATE=30
VIDEO=bad-apple.webm

if test -f "$VIDEO"; then
    echo "$VIDEO already exists, skipping download"
else
    yt-dlp 'https://www.youtube.com/watch?v=FtutLA63Cp8' -o $VIDEO
fi

rm -rf frames
mkdir frames
ffmpeg -i $VIDEO -vf "scale=44:33" -r $FRAMERATE/1 'frames/%04d.bmp'
