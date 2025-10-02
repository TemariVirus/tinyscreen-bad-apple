from PIL import Image

FILENAME = "framedata"
WIDTH = 96
HEIGHT = 64
frame_var = f"extern uint8_t frame[{WIDTH * HEIGHT // 8}]"

with open(f"{FILENAME}.h", "w") as f:
    f.write(f"{frame_var};")

with open(f"{FILENAME}.cpp", "w") as f:
    f.write(f"#include <inttypes.h>\n\n{frame_var} = {{")

    image = Image.open("frames/0161.bmp")
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
    f.write("\n};\n")
