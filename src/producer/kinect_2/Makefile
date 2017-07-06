CC = g++
CFLAGS = -Wall -std=c++11
#INCLUDE = /usr/local/Cellar/libfreenect/0.5.1/include -I /usr/local/opt/curl/lib
#LIBPATH = -L /usr/local/Cellar/libfreenect/0.5.1/lib -L /usr/local/opt/curl/lib
INCLUDE = -I /usr/local/include -I /usr/local/opt/curl/lib
LIBPATH = -L /usr/local/lib
LIB = -l freenect2 -l curl

devicep: devicep.o
	$(CC) $(CLAGS) $(LIBPATH) devicep.o -o devicep $(LIB)

devicep.o: devicep.cpp
	$(CC) $(CFLAGS) $(INCLUDE) -c devicep.cpp

listener.o: listener.cpp listener.hpp
	$(CC) $(CFLAGS) $(INCLUDE) -c listener.cpp

produce: produce.o listener.o
	$(CC) $(CFLAGS) $(LIBPATH) produce.o listener.o -o produce $(LIB)

produce.o: produce.cpp
	$(CC) $(CFLAGS) $(INCLUDE) -c produce.cpp

