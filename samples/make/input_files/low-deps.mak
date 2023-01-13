file3: deps
	echo here are the deps: > file3
	cat deps >> file3

deps:
	echo mydep1 > deps
