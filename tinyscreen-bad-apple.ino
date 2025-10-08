#define FRAME_RATE 30
#define SCREEN_WIDTH 96
#define SCREEN_HEIGHT 64
#define RLR_UNDEFINED 127
#define FLOAT_SCALE 18
#define FIXED_ONE ((fixed)1 << FLOAT_SCALE)

#include <TinyScreen.h>
#include <SPI.h>
#include <Wire.h>
#include "framedata.h"

typedef uint8_t ReadFn(void*);
typedef uint32_t fixed;

int FRAME_MICROS = 1000000 / FRAME_RATE;
uint8_t BRIGHTNESS = 2;

uint32_t readBits(void* reader, ReadFn* readFn, uint8_t bits) {
  uint32_t value = 0;
  for (uint8_t i = 0; i < bits; i++) {
    value |= ((uint32_t)readFn(reader)) << i;
  }
  return value;
}

uint32_t readBitsRice(void* reader, ReadFn* readFn, uint8_t log2_m) {
  uint32_t value = 0;
  while (readFn(reader)) {
    value += 1;
  }
  value <<= log2_m;
  value |= readBits(reader, readFn, log2_m);
  return value;
}

struct BitReader {
  const size_t* data;
  size_t bit_pos;

  BitReader(const size_t* data)
    : data(data), bit_pos(0) {}

  void reset() {
    bit_pos = 0;
  }
};

uint8_t BitReader_readBit(void* ptr) {
  BitReader* reader = (BitReader*)ptr;
  size_t index = reader->bit_pos / DATA_SIZE;
  size_t shift = reader->bit_pos % DATA_SIZE;
  reader->bit_pos++;
  return (reader->data[index] >> shift) & 1;
}

struct RunLengthReader {
  BitReader* reader;
  size_t runs;
  uint32_t count;
  uint8_t value;

  RunLengthReader(BitReader* reader, size_t runs)
    : reader(reader), runs(runs), count(0), value(RLR_UNDEFINED) {}
};

uint8_t RunLengthReader_readBit(void* ptr) {
  RunLengthReader* reader = (RunLengthReader*)ptr;
  if (reader->runs == 0) {
    return reader->value;
  }
  if (reader->count == 0) {
    if (reader->value == RLR_UNDEFINED) {
      reader->value = BitReader_readBit(reader->reader);
    } else {
      reader->value = 1 - reader->value;
    }
    if (--reader->runs != 0) {
      reader->count = readBitsRice(reader->reader, &BitReader_readBit, COUNT_LOG2_M) + 1;
    }
  }
  reader->count--;
  return reader->value;
}

struct VideoState {
  uint8_t previous_pixels[WIDTH * HEIGHT];
  uint8_t pixels[WIDTH * HEIGHT];
  BitReader reader;
  size_t frame;

  VideoState(const size_t* frames)
    : reader(frames), frame(0) {
    memset(pixels, 0, WIDTH * HEIGHT);
  }

  void reset() {
    memset(pixels, 0, WIDTH * HEIGHT);
    reader.reset();
    frame = 0;
  }

  void nextFrame() {
    bool use_col_major = readBits((void*)&reader, &BitReader_readBit, 1);
    // This is limited to just the previous 1 frame to reduce code size
    uint8_t prev_frame_index = readBits((void*)&reader, &BitReader_readBit, SELECT_BITS);
    if (prev_frame_index) {
      memcpy(previous_pixels, pixels, WIDTH * HEIGHT);
    } else {
      memset(previous_pixels, 0, WIDTH * HEIGHT);
    }

    size_t runs = readBitsRice(&reader, &BitReader_readBit, RUN_LEN_LOG2_M) + 1;
    RunLengthReader rlr = RunLengthReader(&reader, runs);
    for (size_t i = 0; i < HEIGHT * WIDTH; i++) {
      size_t index = i;
      if (use_col_major) {
        size_t x = i / HEIGHT;
        size_t y = i % HEIGHT;
        index = y * WIDTH + x;
      }
      uint8_t diff = RunLengthReader_readBit(&rlr) ? 1 : 0;
      pixels[index] = previous_pixels[index] ^ diff;
    }
  }

  void drawFrame(TinyScreen* display) {
    // TODO: smooth out the B&W frame to prevent strong aliasing effects
    nextFrame();
    display->goTo(0, 0);
    display->startData();

    // Bilinear interpolation to scale the image
    uint16_t scaledRow[SCREEN_WIDTH];
    for (int y = 0; y < SCREEN_HEIGHT; y++) {
      fixed srcY = ((fixed)y * (HEIGHT - 1) << FLOAT_SCALE) / (SCREEN_HEIGHT - 1);
      int y1 = srcY >> FLOAT_SCALE;
      int y2 = (y1 < HEIGHT - 1) ? y1 + 1 : y1;
      fixed yFrac = srcY - ((fixed)y1 << FLOAT_SCALE);

      for (int x = 0; x < SCREEN_WIDTH; x++) {
        fixed srcX = ((fixed)x * (WIDTH - 1) << FLOAT_SCALE) / (SCREEN_WIDTH - 1);
        int x1 = srcX >> FLOAT_SCALE;
        int x2 = (x1 < WIDTH - 1) ? x1 + 1 : x1;
        fixed xFrac = srcX - ((fixed)x1 << FLOAT_SCALE);

        uint8_t p11 = pixels[y1 * WIDTH + x1];
        uint8_t p21 = pixels[y1 * WIDTH + x2];
        uint8_t p12 = pixels[y2 * WIDTH + x1];
        uint8_t p22 = pixels[y2 * WIDTH + x2];

        fixed top = (fixed)p11 * (FIXED_ONE - xFrac) + (fixed)p21 * xFrac;
        fixed bottom = (fixed)p12 * (FIXED_ONE - xFrac) + (fixed)p22 * xFrac;
        fixed grey = (top >> FLOAT_SCALE) * (FIXED_ONE - yFrac) + (bottom >> FLOAT_SCALE) * yFrac;
        if (grey >= FIXED_ONE) {
          grey = FIXED_ONE - 1;
        }
        uint16_t b = grey >> (FLOAT_SCALE - 5);
        uint16_t g = grey >> (FLOAT_SCALE - 6);
        uint16_t r = grey >> (FLOAT_SCALE - 5);
        scaledRow[x] = (b << 11) | (g << 5) | r;
      }
      display->writeBuffer((uint8_t*)scaledRow, SCREEN_WIDTH * 2);
    }

    display->endTransfer();
    if (++frame == FRAME_COUNT) {
      reset();
    }
  }
};

TinyScreen display = TinyScreen(TinyScreenPlus);
VideoState video_state = VideoState(frames);
unsigned long last_micros;

void setup(void) {
  SerialUSB.begin(9600);
  Wire.begin();
  Serial.begin(9600);
  display.begin();
  display.setFlip(true);
  display.setBitDepth(TSBitDepth16);
  display.setBrightness(BRIGHTNESS);
  last_micros = micros();
}

void loop() {
  video_state.drawFrame(&display);
  SerialUSB.print("Frame: ");
  SerialUSB.print(video_state.frame);
  SerialUSB.print(", ");

  unsigned long elapsed = micros() - last_micros;
  SerialUSB.print("Render time: ");
  SerialUSB.print(elapsed);
  SerialUSB.println("us");

  waitForNextFrame();
}

void waitForNextFrame() {
  // Underflow is fine here as we only take the difference,
  // which is almost guaranteed to not overflow (70mins for a frame is crazy).
  unsigned long elapsed = micros() - last_micros;
  if (FRAME_MICROS > elapsed) {
    unsigned long remaining_milis = (FRAME_MICROS - elapsed) / 1000;
    uint16_t remainder = (FRAME_MICROS - elapsed) % 1000;
    delay(remaining_milis + (remainder > 500));
  }
  last_micros = micros();
}
