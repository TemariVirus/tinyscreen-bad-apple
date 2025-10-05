#define FRAME_RATE    15

#include <TinyScreen.h>
#include <SPI.h>
#include <Wire.h>
#include "framedata.h"

int FRAME_MICROS = 1000000 / FRAME_RATE;
uint8_t BRIGHTNESS = 2;

struct BitReader {
  const size_t* data;
  size_t bit_pos;

  BitReader(const size_t* data) : data(data), bit_pos(0) {}

  uint32_t readBits(uint8_t n) {
    uint32_t value = 0;
    for (uint8_t i = 0; i < n; i++) {
      size_t index = bit_pos / DATA_SIZE;
      size_t shift = bit_pos % DATA_SIZE;
      uint8_t bit = (data[index] >> shift) & 1;
      value |= (bit << i);
      bit_pos++;
    }
    return value;
  }
};

struct VideoState {
  uint8_t pixels[WIDTH * HEIGHT];
  size_t frame;
  BitReader frame_reader;
  BitReader len_reader;

  VideoState(const size_t* frames, const size_t* lens) :
    frame(0), frame_reader(frames), len_reader(lens) {
    memset(pixels, 0, WIDTH * HEIGHT);
  }

  void reset() {
    memset(pixels, 0, WIDTH * HEIGHT);
    frame = 0;
    frame_reader.bit_pos = 0;
    len_reader.bit_pos = 0;
  }
};

TinyScreen display = TinyScreen(TinyScreenPlus);
VideoState video_state = VideoState(frames, lens);
unsigned long last_micros;

void setup(void) {
  SerialUSB.begin(9600);
  Wire.begin();
  Serial.begin(9600);
  display.begin();
  display.setFlip(true);
  display.setBitDepth(TSBitDepth8);
  display.setBrightness(BRIGHTNESS);
  display.clearScreen();
  last_micros = micros();
}

void loop() {
  drawFrame(&video_state);
  if (++video_state.frame == FRAME_COUNT) {
    video_state.reset();
    display.clearScreen();
  }

  unsigned long elapsed = micros() - last_micros;
  SerialUSB.print("Render time: ");
  SerialUSB.print(elapsed);
  SerialUSB.println("us");

  waitForNextFrame();
}

void drawFrame(VideoState* state) {
  display.startData();

  size_t len = state->len_reader.readBits(LEN_SIZE);
  for (size_t i = 0; i < len; i++) {
    uint8_t x = state->frame_reader.readBits(7);
    uint8_t y = state->frame_reader.readBits(6);
    state->pixels[y * WIDTH + x] ^= 0xFF;
    display.drawPixel(x, y, state->pixels[y * WIDTH + x]);
  }

  display.endTransfer();
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
