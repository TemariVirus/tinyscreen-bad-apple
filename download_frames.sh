#!/usr/bin/env bash

FRAMERATE=15
VIDEO=bad-apple.webm

if test -f "$VIDEO"; then
    echo "$VIDEO already exists, skipping download"
else
    yt-dlp 'https://www.youtube.com/watch?v=FtutLA63Cp8' -o $VIDEO
fi

rm -rf frames
mkdir frames
# ffmpeg -i $VIDEO -vf "scale=-1:64,pad=width=96:x=-1:color=black" -r $FRAMERATE/1 'frames/%04d.bmp'
ffmpeg -i $VIDEO -vf "scale=96:64" -r $FRAMERATE/1 'frames/%04d.bmp'  # Video is a bit elongated, but looks better than padding
