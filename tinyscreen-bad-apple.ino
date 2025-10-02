#define FRAME_RATE    15
#define WIDTH         96
#define HEIGHT        64


#include <TinyScreen.h>
#include <SPI.h>
#include <Wire.h>
#include "framedata.h"

int FRAME_MICROS = 1000000 / FRAME_RATE;
uint8_t BRIGHTNESS = 2;

TinyScreen display = TinyScreen(TinyScreenPlus);
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
  drawFrame();

  unsigned long elapsed = micros() - last_micros;
  SerialUSB.print(elapsed);
  SerialUSB.println("us");

  waitForNextFrame();
}

void drawFrame() {
  display.goTo(0, 0);
  display.startData();

  uint8_t buf[WIDTH * HEIGHT];
  for (size_t i = 0; i < WIDTH * HEIGHT; i++) {
    size_t index = i / 8;
    int shift = i % 8;
    int bit = (frame[index] >> shift) & 1;
    buf[i] = bit * TS_8b_White;
  }
  display.writeBuffer(buf, WIDTH * HEIGHT);

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
