#include <libfreenect2/frame_listener.hpp>
#include <string>

#ifndef VT_KINECT_2_LISTENER
#define VT_KINECT_2_LISTENER

class UploadFrameListener : public libfreenect2::FrameListener {
public:
  UploadFrameListener(std::string address, uint16_t port);
  bool onNewFrame(libfreenect2::Frame::Type type, libfreenect2::Frame * frame);
  ~UploadFrameListener() {}
private:
  std::string address;
  uint16_t port;
};

#endif
