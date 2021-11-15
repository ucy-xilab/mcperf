all: spin

spin: spin.c
	gcc spin.c -O0 -o spin
