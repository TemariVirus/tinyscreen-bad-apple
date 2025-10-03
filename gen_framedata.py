from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 308
WIDTH = 96
HEIGHT = 64
DATA_SIZE = 32  # sizeof(size_t) in bits

assert (WIDTH * HEIGHT) % DATA_SIZE == 0
frames_var = "extern const size_t frames[]"


class BitWriter:
    assert DATA_SIZE % 4 == 0
    HEX_LEN = DATA_SIZE // 4
    ROW_LEN = 8

    def __init__(self, file: TextIO) -> None:
        self.file = file
        self.written = 0
        self.data = 0
        self.pos = 0

    def flush(self) -> None:
        if self.pos > 0:
            if self.written % self.ROW_LEN == 0:
                self.file.write("\n    ")
            self.file.write(f"0x{self.data:0{self.HEX_LEN}x}, ")
            self.data = 0
            self.pos = 0
            self.written += 1

    def write(self, bit: int) -> None:
        assert bit in (0, 1)
        self.data |= bit << self.pos
        self.pos += 1
        if self.pos == DATA_SIZE:
            self.flush()


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 128 else 1, mode="1")
    image.close()
    return list(bw_image.getdata())


def write_frame(writer: BitWriter, pixels: list[int]) -> None:
    for pixel in pixels:
        writer.write(pixel)
    writer.flush()


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
    bit_writer = BitWriter(f)
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        write_frame(bit_writer, frame)
    bit_writer.flush()
    f.write("\n};\n")
