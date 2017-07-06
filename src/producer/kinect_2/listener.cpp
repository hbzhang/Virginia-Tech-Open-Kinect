#include "listener.hpp"

#include <curl/curl.h>
#include <syslog.h>
#include <cmath>

UploadFrameListener::UploadFrameListener(std::string address, uint16_t port) {
  this->address = address;
  this->port = port;
}

/*
Converts raw kinect video data of a given size into a BMP. The BMP is
returned as a FILE object that has a heap allocated block of memory
under it.
*/
FILE * video_to_bmp(libfreenect2::Frame * frame, size_t * size) {
  const unsigned char * video = frame->data;
  const uint32_t video_width = frame->width;
  const uint32_t video_height = frame->height;
  const uint32_t video_pixel_size = frame->bytes_per_pixel;
  const uint32_t video_size = video_width * video_height * video_pixel_size;
  
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

  char * buffer = new char[file_size];
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
  uint8_t * video_safe_backwards = new uint8_t[video_size];
  for (size_t i = 0; i < video_size; i++) {
    video_safe_backwards[i] = video_safe[video_size - i - 1];
  }
  // Color Rows
  uint8_t empty[4] = {0};
  for (size_t row = 0; row < video_height; row++) {
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


bool UploadFrameListener::onNewFrame(libfreenect2::Frame::Type type, libfreenect2::Frame * frame) {
  if (type != libfreenect2::Frame::Color) {
    return false;
  }

  CURL * curl = curl_easy_init();
  curl_easy_setopt(curl, CURLOPT_URL, address.c_str());
  curl_easy_setopt(curl, CURLOPT_PORT, port);
  curl_easy_setopt(curl, CURLOPT_UPLOAD, 1L);

  size_t size = 0;
  
  FILE * bmp = video_to_bmp(frame, &size);

  curl_easy_setopt(curl, CURLOPT_READDATA, bmp);
  curl_easy_setopt(curl, CURLOPT_INFILESIZE_LARGE, size);
  CURLcode result = curl_easy_perform(curl);
  if (result == CURLE_COULDNT_CONNECT) {
    syslog(LOG_ERR, "Failure: Could not connect to %s:%d\n", address.c_str(), port);
    return false;
  } else if (result != CURLE_OK) {
    syslog(LOG_ERR, "Failure: %s\n", curl_easy_strerror(result));
    return false;
  }

  double speed;
  double time;
  curl_easy_getinfo(curl, CURLINFO_SPEED_UPLOAD, &speed);
  curl_easy_getinfo(curl, CURLINFO_TOTAL_TIME, &time);
  printf("Speed: %.3f bytes per second during %.3f seconds.\n", speed, time);

  fclose(bmp);
  curl_easy_cleanup(curl);
  
  return false;
}
