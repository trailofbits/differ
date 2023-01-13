.PHONY: all

all: file1 file2 file3

file1:
	echo hello world > file1

file2:
	echo goodbye world > file2

file3: deps
	echo here are the deps: > file3
	cat deps >> file3

deps:
	echo mydep1 > deps
