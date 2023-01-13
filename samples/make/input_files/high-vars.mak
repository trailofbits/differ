
cycle = 1
build_dir := ${CURDIR}/build/${cycle}


install: file1
	mkdir -p ${build_dir}
	cp file1 ${build_dir}

file1:
	echo file1 > file1
