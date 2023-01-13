include med-phony.mak

file4: file3
	echo this is file4 > file4
	cat file3 >> file4
