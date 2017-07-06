#include <stdio.h>
#include "libfreenect.h"

int main(int argc, char **argv) {
  freenect_context * ctx;
  
  freenect_init(&ctx, NULL);
  
  printf("%d\n", freenect_num_devices(ctx));
  
  freenect_shutdown(ctx);
  
  return 0;
}
