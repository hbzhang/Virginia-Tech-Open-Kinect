#include <iostream>
#include <string>
#include <libfreenect2/libfreenect2.hpp>
#include "listener.hpp"
#include <signal.h>

static bool RUNNING = true;

void sigint_handler(int s) {
  RUNNING = false;
}

int main(int argc, char * argv[]) {
  std::string address;
  uint16_t port;
  if (argc == 3) {
    address = argv[1];
    char ** endptr = NULL;
    port = strtol(argv[2], endptr, 10); 
    if (endptr != NULL) {
      return -1;
    }
  } else if (argc == 1) {
    address = "localhost";
    port = 5000;
  } else {
    printf("Usage:prog [destination-address] [destination-port]\n");
    return -1;
  }

  signal(SIGINT, sigint_handler);

  libfreenect2::Freenect2 freenect2;
  if (!freenect2.enumerateDevices()) {
    printf("No devices found.\n");
    return -1;
  }

  std::string serial = freenect2.getDefaultDeviceSerialNumber();
  libfreenect2::Freenect2Device * dev = freenect2.openDevice(serial);
  if (!dev) {
    printf("Device could not be opened.\n");
    return -1;
  }
  UploadFrameListener listener(address, port);
  dev->setColorFrameListener(&listener);

  if (!dev->startStreams(1, 0)) {
    printf("Stream could not be opened.");
    return -1;
  }

  while(RUNNING);

  dev->stop();
  dev->close();
}
