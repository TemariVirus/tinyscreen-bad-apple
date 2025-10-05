from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 1478
WIDTH = 96
HEIGHT = 64
DATA_SIZE = 32  # sizeof(size_t) in bits
COUNT_SIZE = 7
RUN_COUNT_SIZE = 9
assert (WIDTH * HEIGHT) % DATA_SIZE == 0

FRAMES_VAR = "extern const size_t frames[]"


class Writer:
    def flush(self) -> None:
        raise NotImplementedError

    def write_bit(self, bit: int) -> None:
        raise NotImplementedError

    def write_int(self, value: int, bits: int) -> None:
        for i in range(bits):
            self.write_bit((value >> i) & 1)


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
    MAX_COUNT = 1 << COUNT_SIZE

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
                # The bits never change from here until the end of the frame, so the length can be inferred
                break
            count = min(RunLengthWriter.MAX_COUNT, count)
            self.writer.write_int(count - 1, COUNT_SIZE)
            self.values = self.values[count:]

    def write_bit(self, bit: int) -> None:
        assert bit in (0, 1)
        self.values.append(bit)


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 192 else 1, mode="1")
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


def write_frame(writer: Writer, pixels: list[int]) -> None:
    cw = CountingWriter()
    rlw = RunLengthWriter(cw)
    write_row_major(rlw, pixels)
    rlw.flush()
    row_major_len = cw.written
    row_major_runs = rlw.runs

    cw = CountingWriter()
    rlw = RunLengthWriter(cw)
    write_col_major(rlw, pixels)
    rlw.flush()
    col_major_len = cw.written
    col_major_runs = rlw.runs

    use_row_major = row_major_len <= col_major_len
    writer.write_bit(0 if use_row_major else 1)
    runs = row_major_runs if use_row_major else col_major_runs
    assert runs <= (1 << RUN_COUNT_SIZE)
    writer.write_int(runs - 1, RUN_COUNT_SIZE)
    rlw = RunLengthWriter(writer)
    if use_row_major:
        write_row_major(rlw, pixels)
    else:
        write_col_major(rlw, pixels)
    rlw.flush()


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
        f"#define COUNT_SIZE     {COUNT_SIZE}\n"
        f"#define RUN_COUNT_SIZE {RUN_COUNT_SIZE}\n",
    )
    f.write(f"\n{FRAMES_VAR};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write("#include <TinyScreen.h>\n")
    written = 0

    f.write(f"\n{FRAMES_VAR} = {{")
    bit_writer = BitWriter(f)
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        write_frame(bit_writer, frame)
    bit_writer.flush()
    f.write("\n};\n")
    written += bit_writer.written

    print(f"Wrote {written * 4} bytes to {FILENAME}.cpp")
