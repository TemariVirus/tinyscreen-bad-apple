from typing import TextIO

from PIL import Image

FILENAME = "framedata"
FRAME_COUNT = 1322
WIDTH = 96
HEIGHT = 64
DATA_SIZE = 32  # sizeof(size_t) in bits
COUNT_SIZE = 7


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
        self.value = 0
        self.count = 0
        self.writer = writer

    def flush(self) -> None:
        if self.count == 0:
            return
        self.writer.write_int(self.value, 1)
        self.writer.write_int(self.count - 1, COUNT_SIZE)
        self.count = 0

    def write_bit(self, bit: int) -> None:
        assert bit in (0, 1)
        # Special case for first bit
        if self.count == 0:
            self.value = bit
        if bit != self.value or self.count == RunLengthWriter.MAX_COUNT:
            self.flush()
            self.value = bit
        self.count += 1


def decode_frame(path: str) -> list[int]:
    image = Image.open(path)
    bw_image = image.convert("L").point(lambda x: 0 if x < 128 else 1, mode="1")
    image.close()
    return list(bw_image.getdata())


def write_frame(writer: Writer, pixels: list[int]) -> None:
    for p in pixels:
        writer.write_bit(p)


with open(f"{FILENAME}.h", "w") as f:
    f.write(
        f"#define FRAME_COUNT    {FRAME_COUNT}\n"
        f"#define WIDTH          {WIDTH}\n"
        f"#define HEIGHT         {HEIGHT}\n"
        f"#define DATA_SIZE      {DATA_SIZE}\n"
        f"#define COUNT_SIZE     {COUNT_SIZE}\n",
    )
    f.write(f"\n{FRAMES_VAR};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write("#include <TinyScreen.h>\n")
    written = 0

    f.write(f"\n{FRAMES_VAR} = {{")
    bit_writer = BitWriter(f)
    rl_writer = RunLengthWriter(bit_writer)
    for i in range(1, FRAME_COUNT + 1):
        frame = decode_frame(f"frames/{i:0>4}.bmp")
        write_frame(rl_writer, frame)
    rl_writer.flush()
    bit_writer.flush()
    f.write("\n};\n")
    written += bit_writer.written

    print(f"Wrote {written * 4} bytes to {FILENAME}.cpp")
