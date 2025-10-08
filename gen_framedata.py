from copy import deepcopy
from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 6572
WIDTH = 44
HEIGHT = 33
DATA_SIZE = 32  # sizeof(size_t) in bits
BW_THRESHOLD = 170
RICE_LOG2_M1 = 4
RICE_LOG2_M2 = 5
SELECT_BITS = 1
SKIP_LAST_RUN_LEN = True

FRAMES_VAR = "extern const size_t frames[]"


class Writer:
    def flush(self) -> None:
        raise NotImplementedError

    def write_bit(self, bit: int) -> None:
        raise NotImplementedError

    def write_int(self, value: int, bits: int) -> None:
        for i in range(bits):
            self.write_bit((value >> i) & 1)

    # https://en.wikipedia.org/wiki/Golomb_coding#Rice_coding
    def write_int_rice(self, value: int, rice_log2_m: int) -> None:
        RICE_MASK = (1 << rice_log2_m) - 1
        q = value >> rice_log2_m
        r = value & RICE_MASK
        for _ in range(q):
            self.write_bit(1)
        self.write_bit(0)
        self.write_int(r, rice_log2_m)


class CountingWriter(Writer):
    def __init__(self) -> None:
        self.written = 0

    def flush(self) -> None:
        pass

    def write_bit(self, bit: int) -> None:
        self.written += 1


class BitWriter(Writer):
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

    def write_bit(self, bit: int) -> None:
        assert bit in (0, 1)
        self.data |= bit << self.pos
        self.pos += 1
        if self.pos == DATA_SIZE:
            self.flush()


class RunLengthWriter(Writer):
    def __init__(self, writer: Writer) -> None:
        self.values = []
        self.runs = 0
        self.writer = writer

    def flush(self) -> None:
        while len(self.values) > 0:
            value = self.values[0]
            self.runs += 1
            self.writer.write_int(value, 1)
            try:
                count = self.values.index(1 - value)
            except ValueError:
                if SKIP_LAST_RUN_LEN:
                    # The bits never change from here until the end of the frame, so the length can be inferred
                    break
                count = len(self.values)
            self.writer.write_int_rice(count - 1, RICE_LOG2_M1)
            self.values = self.values[count:]

    def write_bit(self, bit: int) -> None:
        assert bit in (0, 1)
        self.values.append(bit)


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    bw_image = image.convert("L").point(
        lambda x: 0 if x < BW_THRESHOLD else 1, mode="1"
    )
    image.close()
    return list(bw_image.getdata())


def write_row_major(writer: Writer, pixels: list[int]) -> None:
    for p in pixels:
        writer.write_bit(p)


def write_col_major(writer: Writer, pixels: list[int]) -> None:
    for x in range(WIDTH):
        for y in range(HEIGHT):
            p = pixels[y * WIDTH + x]
            writer.write_bit(p)


def write_frame(
    writer: Writer,
    previous_pixels: list[list[int]],
    pixels: list[int],
) -> None:
    best_rlw = RunLengthWriter(writer)
    best_length = int(1e10)
    best_runs = 0
    index = 0
    for i, ps in enumerate(previous_pixels):
        pixels_diff = [pixels[i] ^ ps[i] for i in range(WIDTH * HEIGHT)]

        cw = CountingWriter()
        rlw = RunLengthWriter(cw)
        write_row_major(rlw, pixels_diff)
        rlw2 = deepcopy(rlw)
        rlw.flush()
        if cw.written < best_length:
            best_length = cw.written
            best_rlw = rlw2
            best_runs = rlw.runs
            index = i << 1

        cw = CountingWriter()
        rlw = RunLengthWriter(cw)
        write_col_major(rlw, pixels_diff)
        rlw2 = deepcopy(rlw)
        rlw.flush()
        if cw.written < best_length:
            best_length = cw.written
            best_rlw = rlw2
            best_runs = rlw.runs
            index = (i << 1) + 1

    writer.write_int(index, SELECT_BITS + 1)
    if SKIP_LAST_RUN_LEN:
        writer.write_int_rice(best_runs - 1, RICE_LOG2_M2)
    best_rlw.writer = writer
    best_rlw.flush()


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
        f"#define RICE_LOG2_M1   {RICE_LOG2_M1}\n"
        f"#define RICE_LOG2_M2   {RICE_LOG2_M2}\n",
    )
    f.write(f"\n{FRAMES_VAR};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write("#include <TinyScreen.h>\n")
    written = 0

    f.write(f"\n{FRAMES_VAR} = {{")
    bit_writer = BitWriter(f)
    previous_frames = []
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        write_frame(bit_writer, [[0] * (WIDTH * HEIGHT)] + previous_frames, frame)
        previous_frames.append(frame)
        if len(previous_frames) > (1 << SELECT_BITS) - 1:
            previous_frames.pop(0)
    bit_writer.flush()
    f.write("\n};\n")
    written += bit_writer.written

    print(f"Wrote {written * 4} bytes to {FILENAME}.cpp")
