#!/bin/bash

set -e

OPTS="contract clearloop copyloop multiloop offsetops all"
PROGS="*.b"

# return the average runtime of 10 runs
avgruntime() {
    > tmp.dat
    for i in $(seq 10); do
	$1 < $2 > /dev/null 2>>tmp.dat
    done
    echo "scale=4; ($(tr '\n' '+' < tmp.dat) 0) / 10" | bc
    rm tmp.dat
}

for optimization in $OPTS; do

    for program in $PROGS; do

	if test -f ${optimization}.dat && grep $program ${optimization}.dat >/dev/null; then
	    continue
	fi

	# make sure we have runtime without optimizations
	if [ ! -f ${program}.none.dat ]; then
	    echo "$program without optimization"
	    python optimizr.py none <$program > tmp.c
	    gcc -O0 tmp.c -o tmp
	    avgruntime ./tmp ${program}.in > ${program}.none.dat
	fi

	# run with opt and add improvement to data file
	echo "$program with $optimization"
	python optimizr.py $optimization <$program > tmp.c
	gcc -O0 tmp.c -o tmp
	rm tmp.c
	echo -ne "$program\t" >> ${optimization}.dat
	echo "scale=5; $(avgruntime ./tmp ${program}.in) / $(<${program}.none.dat)" | \
	    bc >> ${optimization}.dat
    done

    # gnuplot!
    echo "plotting ${optimization}.p"
    cat > ${optimization}.p <<EOF
set terminal png
set output "${optimization}.png"
set title "$optimization optimization speedup"
set auto x
set yrange [0:1]
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "speedup over unoptimized version"
plot '${optimization}.dat' using 2:xticlabel(1) notitle
EOF

   gnuplot ${optimization}.p

done

