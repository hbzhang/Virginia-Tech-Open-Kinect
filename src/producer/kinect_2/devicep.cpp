#include <iostream>
#include <libfreenect2/libfreenect2.hpp>

int main() {
  libfreenect2::Freenect2 freenect2;  
  std::cout << freenect2.enumerateDevices() << std::endl;
  
  return 0;
}
