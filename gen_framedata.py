from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 547
WIDTH = 96
HEIGHT = 64
DATA_SIZE = 32  # sizeof(size_t) in bits
LEN_SIZE = 13

assert (WIDTH * HEIGHT) % DATA_SIZE == 0
FRAMES_VAR = "extern const size_t frames[]"
LENS_VAR = "extern const size_t lens[]"


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

    def write_int(self, value: int, bits: int) -> None:
        for i in range(bits):
            self.write((value >> i) & 1)


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 128 else 1, mode="1")
    image.close()
    return list(bw_image.getdata())


def write_frame(
    writer: BitWriter,
    previous_pixels: list[int],
    pixels: list[int],
) -> int:
    diffs = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            i = y * WIDTH + x
            if pixels[i] != previous_pixels[i]:
                writer.write_int(x, 7)
                writer.write_int(y, 6)
                diffs += 1
    return diffs


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
        f"#define LEN_SIZE       {LEN_SIZE}\n",
    )
    f.write(f"\n{FRAMES_VAR};")
    f.write(f"\n{LENS_VAR};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write("#include <TinyScreen.h>\n")

    f.write(f"\n{FRAMES_VAR} = {{")
    bit_writer = BitWriter(f)
    lens = []
    previous_frame = [0] * (WIDTH * HEIGHT)
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        length = write_frame(bit_writer, previous_frame, frame)
        lens.append(length)
        previous_frame = frame
    bit_writer.flush()
    f.write("\n};\n")
    written = bit_writer.written

    bit_writer = BitWriter(f)
    f.write(f"\n{LENS_VAR} = {{")
    for length in lens:
        bit_writer.write_int(length, LEN_SIZE)
    bit_writer.flush()
    f.write("\n};\n")
    written += bit_writer.written

    print(f"Wrote {written * 4} size_t values to {FILENAME}.cpp")
