#include <stdint.h>
#include <inttypes.h>
#include "libfreenect.h"

void depth_cb(freenect_device * dev, void * depth, uint32_t timestamp);
void video_cb(freenect_device * dev, void * video, uint32_t timestamp);
void signal_cb(int signal);
FILE * video_to_bmp(void * video, size_t * size);
int main(int argc, char **argv);
