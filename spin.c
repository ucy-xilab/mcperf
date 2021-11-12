#include <stdlib.h>
#include <time.h>

int main(int argc, char **argv)
{
  int target_duration = atoi(argv[1]);	
  unsigned long start = (unsigned long)time(NULL);
  unsigned long cur;
  do {
    volatile int c;
    for (c=0; c<1000000000; c++);
    cur = (unsigned long)time(NULL);
  } while (cur < start + target_duration);
  return 0;
}
