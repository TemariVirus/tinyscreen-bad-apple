from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 308
WIDTH = 96
HEIGHT = 64
DATA_SIZE = 32  # sizeof(size_t) in bits

assert (WIDTH * HEIGHT) % DATA_SIZE == 0
frames_var = f"extern const size_t frames[][{WIDTH * HEIGHT // DATA_SIZE}]"


def write_frame(f: TextIO, path: str) -> None:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 128 else 255, mode="1")
    pixels = list(bw_image.getdata())
    datas = []

    for i in range(0, len(pixels), DATA_SIZE):
        data = 0
        for j in range(DATA_SIZE):
            if i + j < len(pixels):
                # Set the bit if the pixel is white (255 in 1-bit mode)
                if pixels[i + j] == 255:
                    data |= 1 << j
        datas.append(data)

    for i, data in enumerate(datas):
        if i % 8 == 0:
            f.write("\n    ")
        f.write(f"0x{data:08x}, ")


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
    )
    f.write(f"\n{frames_var};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write(f"#include <TinyScreen.h>\n\n{frames_var} = {{")
    for i in range(1, FRAME_COUNT + 1):
        write_frame(f, f"frames/{i:0>4}.bmp")
    f.write("\n};\n")
