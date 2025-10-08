from copy import deepcopy
from typing import TextIO, cast

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 6572
WIDTH = 47
HEIGHT = 35
BW_THRESHOLD = 64
DATA_SIZE = 32  # sizeof(size_t) in bits
COUNT_LOG2_M = 4
RUN_LEN_LOG2_M = 5
SELECT_BITS = 1

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
        first = True
        while len(self.values) > 0:
            value = self.values[0]
            self.runs += 1
            if first:
                # The value of every run from now on is just a toggle of the previous value
                self.writer.write_int(value, 1)
                first = False
            try:
                count = self.values.index(1 - value)
            except ValueError:
                # The bits never change from here until the end of the frame, so the length can be inferred
                break
            self.writer.write_int_rice(count - 1, COUNT_LOG2_M)
            self.values = self.values[count:]

    def write_bit(self, bit: int) -> None:
        assert bit in (0, 1)
        self.values.append(bit)


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    grey = image.convert("L", colors=256)
    bw = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            pixel = cast(float, grey.getpixel((x, y)))
            if pixel > 256 - BW_THRESHOLD:
                bw.append(1)
                continue
            if pixel < BW_THRESHOLD:
                bw.append(0)
                continue

            black_neighbors = 0
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dy == 0 and dx == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                        neighbor_pixel = cast(float, grey.getpixel((nx, ny)))
                        if neighbor_pixel < 128:
                            black_neighbors += 1
            bw.append(0 if black_neighbors >= 5 else 1)
    image.close()
    return bw


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
    best_rlw = None
    best_length = int(1e15)
    best_runs = 0
    best_index = 0
    for i, prev in enumerate(previous_pixels):
        pixels_diff = [pixels[i] ^ prev[i] for i in range(WIDTH * HEIGHT)]

        cw = CountingWriter()
        rlw = RunLengthWriter(cw)
        write_row_major(rlw, pixels_diff)
        rlw_copy = deepcopy(rlw)
        rlw.flush()
        if cw.written < best_length:
            best_length = cw.written
            best_rlw = rlw_copy
            best_runs = rlw.runs
            best_index = (i << 1) | 0

        cw = CountingWriter()
        rlw = RunLengthWriter(cw)
        write_col_major(rlw, pixels_diff)
        rlw_copy = deepcopy(rlw)
        rlw.flush()
        if cw.written < best_length:
            best_length = cw.written
            best_rlw = rlw_copy
            best_runs = rlw.runs
            best_index = (i << 1) | 1

    writer.write_int(best_index, SELECT_BITS + 1)
    writer.write_int_rice(best_runs - 1, RUN_LEN_LOG2_M)
    assert best_rlw is not None
    best_rlw.writer = writer
    best_rlw.flush()


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
        f"#define COUNT_LOG2_M   {COUNT_LOG2_M}\n"
        f"#define RUN_LEN_LOG2_M {RUN_LEN_LOG2_M}\n"
        f"#define SELECT_BITS    {SELECT_BITS}\n",
    )
    f.write(f"\n{FRAMES_VAR};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write("#include <TinyScreen.h>\n")

    f.write(f"\n{FRAMES_VAR} = {{")
    bit_writer = BitWriter(f)
    previous_frames = []
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        write_frame(bit_writer, [[0] * (WIDTH * HEIGHT)] + previous_frames, frame)
        previous_frames.append(frame)
        if len(previous_frames) >= 1 << SELECT_BITS:
            previous_frames.pop(0)
    bit_writer.flush()
    f.write("\n};\n")

    print(f"Wrote {bit_writer.written * 4} bytes to {FILENAME}.cpp")
