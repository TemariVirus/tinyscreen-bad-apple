from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 308
WIDTH = 96
HEIGHT = 64
frames_var = f"extern const uint8_t frames[][{WIDTH * HEIGHT // 8}]"
frame_count_var = "extern const size_t frame_count"


def write_frame(f: TextIO, path: str) -> None:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 128 else 255, mode="1")
    pixels = list(bw_image.getdata())
    bytes_data = []

    for i in range(0, len(pixels), 8):
        byte = 0
        for j in range(8):
            if i + j < len(pixels):
                # Set the bit if the pixel is white (255 in 1-bit mode)
                if pixels[i + j] == 255:
                    byte |= 1 << j
        bytes_data.append(byte)

    for i, byte in enumerate(bytes_data):
        if i % (WIDTH // 8) == 0:
            f.write("\n    ")
        f.write(f"0x{byte:02x}, ")


with open(f"{FILENAME}.h", "w") as f:
    f.write(f"#define FRAME_COUNT    {FRAME_COUNT}\n\n")
    f.write(f"{frames_var};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write(f"#include <inttypes.h>\n\n{frames_var} = {{")
    for i in range(1, FRAME_COUNT + 1):
        write_frame(f, f"frames/{i:0>4}.bmp")
    f.write("\n};\n")
