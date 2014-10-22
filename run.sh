#!/bin/bash

set -e

OPTS="contract clearloop copyloop multiloop offsetops reorder all"
PROGS="*.b"

# return the average runtime of 10 runs. ignores the slowest of the 10.
avgruntime() {
    > tmp.dat
    TIMEFORMAT="%R"
    for i in $(seq 10); do
	{ time $1 < $2 > $3 2> /dev/null ; } 2>>tmp.dat
    done
    echo "scale=4; ($(sort tmp.dat | head -n-1 | tr '\n' '+') 0) / 9" | bc
}

# measure runtime for all optimizations on all programs
for optimization in $OPTS; do

    for program in $PROGS; do

	if test -f $optimization.dat && grep $program $optimization.dat >/dev/null; then
	    continue
	fi

	# make sure we have runtime without optimizations
	if [ ! -f $program.none.dat -o ! -f $program.out ]; then
	    echo "$program without optimization"
	    python optimizr.py none <$program > tmp.c
	    gcc -O0 tmp.c -o tmp
	    avgruntime ./tmp $program.in $program.out > $program.none.dat
	fi

	# run with opt and add improvement to data file
	echo "$program with $optimization"
	python optimizr.py $optimization <$program > tmp.c
	gcc -O0 tmp.c -o tmp
	rm tmp.c
	echo -ne "$program\t" >> $optimization.dat
	echo -ne "$(avgruntime ./tmp $program.in tmp.out)" >> $optimization.dat
	echo -e "\t$(<$program.none.dat)" >> $optimization.dat

	# verify that the output was correct
	if ! cmp tmp.out $program.out; then
	    echo "EPIC MEGA FAIL"
	    exit 1
	fi
    done

    # gnuplot!
    echo "plotting $optimization.p"
    cat > $optimization.p <<EOF
set terminal png
set output "$optimization.png"
set title "$optimization optimization speedup"
set auto x
set yrange [0:1]
set ytic 0.1
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "speedup over unoptimized version"
plot '$optimization.dat' using (\$2 / \$3):xticlabels(1) notitle
EOF

   gnuplot $optimization.p

done

# plot offsetops and reorder side by side
if test -f offsetops.dat && test -f reorder.dat; then
    echo "plotting offsetops vs reorder"
    > offset_reorder.dat
    for program in $PROGS; do
	echo -ne "$program\t" >> offset_reorder.dat
	echo -ne "$(grep $program offsetops.dat | cut -f2)\t" >> offset_reorder.dat
	echo -ne "$(grep $program reorder.dat | cut -f2,3)\n" >> offset_reorder.dat
    done

    cat > offset_reorder.p <<EOF
set terminal png
set output "offset_reorder.png"
set title "offsetsops and reorder optimization speedup"
set key inside top left box
set auto x
set yrange [0:*]
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "speedup over unoptimized version"
plot 'offset_reorder.dat' using (\$2 / \$4):xticlabel(1) title 'offsets', \
     '' u (\$3 / \$4) title 'offsets and reorder'
EOF

    gnuplot offset_reorder.p
fi

# plot actual runtimes without optimization
echo "plotting runtimes"
> runtime.dat
for program in $PROGS; do
    echo -e "$program\t$(<$program.none.dat)" >> runtime.dat
done

cat > runtime.p <<EOF
set terminal png
set output "runtime.png"
set title "runtime without optimizations"
set auto x
set yrange [0:*]
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "runtime (seconds)"
plot 'runtime.dat' using 2:xticlabel(1) notitle
EOF

gnuplot runtime.p


# plot actual runtimes with and without optimization
> runtime2.dat
for program in $PROGS; do
    echo -ne "$program\t$(<$program.none.dat)\t" >> runtime2.dat
    grep $program all.dat | awk '{print $2}' >> runtime2.dat
done

cat > runtime2.p <<EOF
set terminal png
set output "runtime2.png"
set title "runtime with and without optimizations"
set key inside top left box
set auto x
set yrange [0:*]
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "runtime (seconds)"
plot 'runtime2.dat' using 2:xticlabel(1) title 'no optimization', \
     '' u 3 title 'all optimizations'
EOF

gnuplot runtime2.p

# measure runtime of each program compiled with all compilers
echo $PROGS
for program in $PROGS; do

    touch opt_$program.dat

    # awib-0.4
    if [ -f compilers/awib-0.4.b ] && \
	! grep awib-0.4 opt_$program.dat > /dev/null; then

	# build compiler if needed
	if [ ! -f compilers/awib-0.4 ]; then
	    echo "building awib-0.4"
	    cp compiler/awib-0.4.b tmp.c
	    gcc tmp.c -o tmp
	    ./tmp.c < compilers/awib-0.4.b > compilers/awib-0.4.c
	    gcc -O3 compilers/awib-0.4 -o compilers/awib-0.4
	fi

	# compile program, run and measure runtime
	echo "$program with awib-0.4"
	compilers/awib-0.4 < $program > tmp.c
	gcc -O0 tmp.c -o tmp
	echo -ne "awib-0.4\t" >> opt_$program.dat
	avgruntime ./tmp $program.in tmp.out >> opt_$program.dat
	if ! cmp tmp.out $program.out; then
	    echo "EPIC MEGA FAIL"
	    exit 1
	fi
    else
	echo "skipping awib-0.4"
    fi

    # hamster-0.4
    if [ -d compilers/hamster_v.0.4 ] && \
	! grep hamster-0.4 opt_$program.dat > /dev/null; then

	# compile, run, measure
	echo "$program with hamster-0.4"
	mzscheme compilers/hamster_v.0.4/bf-compiler.scm ansi_c $program > tmp.c
	gcc -O0 tmp.c -o tmp
	echo -ne "hamster-0.4\t" >> opt_$program.dat
	avgruntime ./tmp $program.in tmp.out >> opt_$program.dat
	if ! cmp tmp.out $program.out; then
	    echo "EPIC MEGA FAIL"
	    exit 1
	fi
    else
	echo "skipping hamster-0.4"
    fi

    # esotope
    if [ -d compilers/bfc ] && \
	! grep esotope opt_$program.dat > /dev/null; then

	# compile, run, measure
	echo "$program with esotope"
	PYTHONPATH=compilers/bfc compilers/bfc/esotope-bfc $program > tmp.c
	gcc -O0 tmp.c -o tmp
	echo -ne "esotope\t" >> opt_$program.dat
	avgruntime ./tmp $program.in tmp.out >> opt_$program.dat
	if ! cmp tmp.out $program.out; then
	    echo "EPIC MEGA FAIL"
	    exit 1
	fi
    else
	echo "skipping esotope"
    fi

    # bff4
    if [ -f compilers/bff4.c ] && \
	! grep bff4 opt_$program.dat > /dev/null; then

	# compile, run, measure
	echo "$program with bff4"
	gcc -O3 compilers/bff4.c -o compilers/bff4
	(tr -d '!' < $program; echo '!'; cat $program.in) > tmp.in
	echo -ne "bff4\t" >> opt_$program.dat
	avgruntime compilers/bff4 tmp.in tmp.out >> opt_$program.dat
	if ! cmp tmp.out $program.out; then
	    echo "EPIC MEGA FAIL"
	    exit 1
	fi
    else
	echo "skipping bff4"
    fi

    # optimizr.py
    if ! grep optimizr.py opt_$program.dat > /dev/null; then

	# grab runtime from previous run
	echo "$program with all"
	echo -ne "optimizr\t" >> opt_$program.dat
	grep $program all.dat | awk '{print $2}' >> opt_$program.dat
    fi

    # plot runtimes for the compilers
    echo "plotting opt_$program.p"
    cat > opt_$program.p <<EOF
set terminal png
set output "opt_$program.png"
set title "runtime of $program with different compilers "
set auto x
set yrange [0:*]
set style data histogram
set style histogram cluster gap 1
set style fill solid 1.0 noborder
set grid y
set xtic rotate by -45 scale 0
set boxwidth 0.9
set ylabel "runtime (seconds)"
plot 'opt_$program.dat' using 2:xticlabel(1) notitle
EOF

    gnuplot opt_$program.p

done
