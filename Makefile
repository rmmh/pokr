accel.so: accel.c accel.h
	$(CC) -g -O2 -Wall -shared -o accel.so -fPIC -lm accel.c
