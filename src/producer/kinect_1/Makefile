CC = gcc
CFLAGS = -Wall -std=c99
INCLUDE = -I ~/libfreenect/include -I /usr/local/opt/curl/lib
LIBPATH = -L ~/libfreenect/build/lib -L /usr/local/opt/curl/lib
LIB = -l freenect -l curl

devicep: devicep.o
	$(CC) $(CLAGS) $(LIBPATH) $(LIB) devicep.o -o devicep

devicep.o: devicep.c
	$(CC) $(CFLAGS) $(INCLUDE) -c devicep.c

produce: produce.o fmemopen.o
	$(CC) $(CFLAGS) $(LIBPATH) $(LIB) produce.o fmemopen.o -o produce

produce.o: produce.c produce.h
	$(CC) $(CFLAGS) $(INCLUDE) -c produce.c

fmemopen.o: fmemopen.c fmemopen.h
	$(CC) $(CFLAGS) $(LIBPATH) $(LIB) -c fmemopen.c

test_post : test_post.o
	$(CC) $(CFLAGS) $(LIBPATH) $(LIB) test_post.o -o test_post

test_post.o : test_post.c
	$(CC) $(CFLAGS) $(INCLUDE) -c test_post.c

