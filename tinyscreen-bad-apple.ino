#define FRAME_RATE 30

#include <TinyScreen.h>
#include <SPI.h>
#include <Wire.h>
#include "framedata.h"

typedef uint8_t ReadFn(void*);

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
    : reader(reader), runs(runs), count(0), value(0) {}
};

uint8_t RunLengthReader_readBit(void* ptr) {
  RunLengthReader* reader = (RunLengthReader*)ptr;
  if (reader->runs == 0) {
    return reader->value;
  }
  if (reader->count == 0) {
    reader->value = BitReader_readBit(reader->reader);
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
      uint8_t diff = RunLengthReader_readBit(&rlr) ? 0xFF : 0x00;
      pixels[index] = previous_pixels[index] ^ diff;
    }
  }

  void drawFrame(TinyScreen* display) {
    // TODO: smooth out the B&W frame to prevent strong aliasing effects
    nextFrame();

    for (int i = 0; i < HEIGHT; i++) {
      display->goTo(0, i);
      display->startData();
      display->writeBuffer(&pixels[i * WIDTH], WIDTH);
      display->endTransfer();
    }

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
  display.setBitDepth(TSBitDepth8);
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
