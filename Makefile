
compress.so: compress.c
	gcc -O2 -Wall -shared -o compress.so -fPIC compress.c
