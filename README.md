# tinyscreen-bad-apple

WORK-IN-PROGRESS

Let's see if we can play Bad Apple on the TinyScreen+'s 96x64 display at 15 FPS, or maybe even 30 FPS! Unfortunately it has no speakers, so no sound :(

## Run it on your own TinyScreen+

1. Install ffmpeg, python3, and then install pillow with pip. (or use the flake with `nix develop`)
2. Install the Arduino IDE and set up the TinyScreen+ board support (TODO: link to instructions)
3. Run `download_frames.sh` to get the frames from YouTube.
4. Run `python gen_framedata.py` to generate C++ code for the frames.
5. Open `tinyscreen-bad-apple.ino` in the Arduino IDE, and compile and upload it to your TinyScreen+.
