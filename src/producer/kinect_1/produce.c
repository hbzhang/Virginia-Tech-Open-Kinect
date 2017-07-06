/*
This program reads data from a first generation Kinect sensor,
converts it into an image file, and sends it over HTTP to a given IP
and port. By default, it sends the data to localhost port 5000.
*/

#include <stdio.h>
#include <stdint.h>
#include <signal.h>
#include <inttypes.h>
#include <unistd.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <syslog.h>
#include "libfreenect.h"
#include <curl/curl.h>
#include "produce.h"
#include "fmemopen.h"

/*
The address and port data will be sent to are stored in these global
variables.
*/
char * ADDR;
uint16_t PORT;

/*
These eight constants are used to convert the raw sensor data from the
Kinect into an image file.
*/
const uint32_t depth_width = 640;
const uint32_t depth_height = 480;
const uint32_t depth_pixel_size = sizeof(uint8_t) * 2;
const uint32_t depth_size = depth_width * depth_height * depth_pixel_size;

const uint32_t video_width = 640;
const uint32_t video_height = 480;
const uint32_t video_pixel_size = sizeof(uint8_t) * 3;
const uint32_t video_size = video_width * video_height * video_pixel_size;

/*
As long as this variable is true, the program will continue
running. It's volatile because it can be changed from multiple
threads. (I'm not sure this is the right way to do shared memory,
shouldn't there be a lock or something?)
*/
volatile int running = 1;

/*
A callback that tells the program to stop under SIGINT, SIGTERM, and SIGQUIT.
*/
void signal_cb(int signal) {
  running = (signal != SIGINT) && (signal != SIGTERM) && (signal != SIGQUIT);
}

/*
An empty callback that ignores any depth information provided.
*/
void depth_cb(freenect_device * dev, void * depth, uint32_t timestamp) {
  //write(1, (uint8_t *) depth, depth_size);
}

/*
Converts raw kinect video data of a given size into a BMP. The BMP is
returned as a FILE object that has a heap allocated block of memory
under it.
*/
FILE * video_to_bmp(void * video, size_t * size) {
  const char header_field[2] = {'B', 'M'};
  const uint32_t file_header_size = 14;
  const uint16_t application_number = 0;
  const uint32_t dib_header_size = 40;
  const uint32_t color_row_start = file_header_size + dib_header_size;
  const uint16_t bits_per_pixel = 24;
  const uint32_t row_size = floor((bits_per_pixel * video_width + 31.0) / 32) * 4; // Rows are padded in BMP, so the row length is a little longer than the video width
  const uint32_t pixel_array_size = row_size * video_height;
  const uint32_t file_size = pixel_array_size + dib_header_size + file_header_size;

  const uint16_t color_planes = 1;
  const uint32_t bytes_per_pixel = 3;
  const uint32_t compression = 0;
  const uint32_t color_size = 0;
  const uint32_t important_color_size = 0;
  const int32_t pixel_per_meter = 0;

  void * buffer = malloc(file_size);
  FILE * file = fmemopen(buffer, file_size, "wb");
  if (file == NULL) exit(errno);
  
  int ret = 0;
  // Bitmap File Header
  ret = fwrite(&header_field, 2, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&file_size, 4, 1, file); // The file size in bytes.
  if (ret == -1) exit(errno);    
  ret = fwrite(&application_number, 2, 1, file); // Application Number
  if (ret == -1) exit(errno);    
  ret = fwrite(&application_number, 2, 1, file); // Application Number
  if (ret == -1) exit(errno);    
  ret = fwrite(&color_row_start, 4, 1, file);
  if (ret == -1) exit(errno);    
  
  // DIB HEADER (BITMAPINFOHEADER)
  ret = fwrite(&dib_header_size, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&video_width, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&video_height, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&color_planes, 2, 1, file); // Required Value
  if (ret == -1) exit(errno);    
  ret = fwrite(&bits_per_pixel, 2, 1, file); // Bits per pixel.
  if (ret == -1) exit(errno);    
  ret = fwrite(&compression, 4, 1, file); // Compression (None)
  if (ret == -1) exit(errno);    
  ret = fwrite(&video_size, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&pixel_per_meter, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&pixel_per_meter, 4, 1, file);
  if (ret == -1) exit(errno);    
  ret = fwrite(&color_size, 4, 1, file); // The number of colors. (zero means 2^n)
  if (ret == -1) exit(errno);    
  ret = fwrite(&important_color_size, 4, 1, file); // The number of important colors. (zero means all colors are important)
  if (ret == -1) exit(errno);

  uint8_t * video_safe = (uint8_t *) video;
  uint8_t * video_safe_backwards = calloc(video_size, 1);
  for (int i = 0; i < video_size; i++) {
    video_safe_backwards[i] = video_safe[video_size - i - 1];
  }
  // Color Rows
  uint8_t empty[4] = {0};
  for (int row = 0; row < video_height; row++) {
    // Fwrite Pixels
    ret = fwrite(video_safe_backwards, 1, bytes_per_pixel * video_width, file);
    if (ret == -1) exit(errno);
    // Fwrite Padding
    ret = fwrite(empty, 1, (row_size - (video_width * bytes_per_pixel)), file);
    if (ret == -1) exit(errno);    
    // Move Up a Row
    video_safe_backwards += video_width * bytes_per_pixel;
  }

  //ret = fclose(file); Don't close because it frees the buffer.
  //if (ret == -1) exit(errno);
  *size = file_size;
  FILE * read_file = fmemopen(buffer, *size, "rb");
  if (file == NULL) exit(errno);
  return read_file;
}

/*
A callback that takes raw sensor data, converts it into a BMP, and
sends it over the network.
*/
void video_cb(freenect_device * dev, void * video, uint32_t timestamp) {
  CURL * curl = curl_easy_init();
  curl_easy_setopt(curl, CURLOPT_URL, ADDR);
  curl_easy_setopt(curl, CURLOPT_PORT, PORT);
  curl_easy_setopt(curl, CURLOPT_UPLOAD, 1L);

  size_t size = 0;
  
  FILE * bmp = video_to_bmp(video, &size);

  curl_easy_setopt(curl, CURLOPT_READDATA, bmp);
  curl_easy_setopt(curl, CURLOPT_INFILESIZE_LARGE, size);
  CURLcode result = curl_easy_perform(curl);
  if (result == CURLE_COULDNT_CONNECT) {
    syslog(LOG_ERR, "Failure: Could not connect to %s:%d\n", ADDR, PORT);
    return;
  } else if (result != CURLE_OK) {
    syslog(LOG_ERR, "Failure: %s\n", curl_easy_strerror(result));
  }

  double speed;
  double time;
  curl_easy_getinfo(curl, CURLINFO_SPEED_UPLOAD, &speed);
  curl_easy_getinfo(curl, CURLINFO_TOTAL_TIME, &time);
  printf("Speed: %.3f bytes per second during %.3f seconds.\n", speed, time);

  fclose(bmp);
  curl_easy_cleanup(curl);
}



/*
The main function parses the shell arguments, sets up the signal
handling code, initializes all libraries, sets the program into a main
loop, and then cleans up resources when the main loop ends.
*/
int main(int argc, char **argv) {
  if (argc == 3) {
    ADDR = argv[1];
    char ** endptr = NULL;
    PORT = strtol(argv[2], endptr, 10); 
    if (endptr != NULL) {
      return -1;
    }
  } else if (argc == 1) {
    ADDR = "localhost";
    PORT = 5000;
  } else {
    printf("Usage:prog [destination-address] [destination-port]\n");
    return -1;
  }
  
  signal(SIGINT, signal_cb);
  signal(SIGTERM, signal_cb);
  signal(SIGQUIT, signal_cb);

  if(curl_global_init(CURL_GLOBAL_ALL) != CURLE_OK) {
    printf("cURL could not be initialized\n");
    return -1;
  }

  int ret;
  freenect_context * ctx;
  ret = freenect_init(&ctx, NULL);
  if (ret < 0) return ret;
  printf("Freenect Initialized\n");

  freenect_select_subdevices(ctx, FREENECT_DEVICE_CAMERA);
  freenect_device * sensor;
  ret = freenect_open_device(ctx, &sensor, 0);
  if (ret < 0) return ret;
  printf("Device Initialized\n");
  ret = freenect_set_video_mode(sensor,
				freenect_find_video_mode(FREENECT_RESOLUTION_MEDIUM, FREENECT_VIDEO_RGB));
  if (ret < 0) return ret;
  printf("Video Mode Set\n");
  freenect_set_depth_callback(sensor, depth_cb);
  freenect_set_video_callback(sensor, video_cb);

  ret = freenect_start_depth(sensor);
  if (ret < 0) return ret;
  printf("Depth stream started.");
  ret = freenect_start_video(sensor);
  if (ret < 0) return ret;
  printf("Video stream started.");

  // --- BODY ---
  while (running && !freenect_process_events(ctx)) {
  
  }
  
  ret = freenect_stop_depth(sensor);
  if (ret < 0) return ret;
  ret = freenect_stop_video(sensor);
  if (ret < 0) return ret;

  ret = freenect_close_device(sensor);
  if (ret < 0) return ret;
  ret = freenect_shutdown(ctx);
  if (ret < 0) return ret;


  
  return 0;
}
