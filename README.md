Brainfuck Optimization
======================

An examination of brainfuck compiler optimization techniques.

This stuff resulted in a blog post that will at some point be
published somewhere. Maybe.


Sample programs
---------------

To meaningfully evaluate the impact different optimization techniques
can have on performance, we need a set of brainfuck programs that are
sufficiently non-trivial for optimization to make sense.

### awib-0.4

[Awib](http://code.google.com/p/awib/), by yours truly, is a brainfuck
compiler written in brainfuck. It has a bunch of bells and whistles
and is, in my highly biased opinion, awesome. In our benchmarks we run
awib-0.4 with itself as input using the lang_java backend. In other
words: it compiles itself from brainfuck into the Java programming
language.

### factor.b

The perhaps most useful brainfuck program I've ever seen is Brian
Raiter's
[factor.b](http://www.muppetlabs.com/~breadbox/bf/factor.b.txt). A
brainfuck implementation of coreutil's factor utility, factor.b breaks
arbitrarily large integers into the prime factors. In our case we run
it with the number 133333333333337 as input, which factors into 397,
1279 and 262589699.

### mandelbrot.b

Erik Bosman's [mandelbrot
implementation](http://esoteric.sange.fi/brainfuck/utils/mandelbrot/mandelbrot.b)
generates a 128x48 ascii graphics mandelbrot fractal. The program
appears to have been generated using
[CPP macros](http://esoteric.sange.fi/brainfuck/utils/mandelbrot/), as
opposed to being fully "hand-written" in brainfuck. It accepts no
input and is run accordingly in our benchmarks.

### hanoi.b

Similar to the mandelbrot implementation, Clifford Wold's [towers of
hanoi solver](http://www.clifford.at/bfcpu/hanoi.bf) was implemented
[using a higher-level
language](http://www.clifford.at/bfcpu/hanoi.html), which was then
compiled into brainfuck code. It offers snazzy visualizations on VT100
terminals. No input required here either.

### dbfi.b

Daniel Cristofani's [dbfi](http://www.hevanet.com/cristofd/bf/dbfi.b)
is a brainfuck interpreter written in brainfuck. In our benchmark we
run it with a very special input: we let it interpret a copy of
itself, which in turn interprets a dummy program called
[hi123](http://mazonka.com/brainf/hi123). This somewhat confusing
setup is sometimes referred to as sisihi123 and appears to first have
been used by Oleg Mazonka when benchmarking his interpreter,
[bff4](http://mazonka.com/brainf/).

### long.b

A dummy program that does nothing useful but takes quite a while to
terminate. Like the sisihi123 combo,
[long.b](http://mazonka.com/brainf/long.b) also appears to have been
created by Mazonka for benchmarking purposes.

Scripts
-------

optimizr.py
: An optimizing brainfuck-to-C compiler

analyze.py
: Silly little script that produces some simple code stats for a
brainfuck program

run.sh
: Runs the optimizer and analyzer on all brainfuck programs. Produces
pretty graphs with gnuplot.

Usage
-----

    $ bash run.sh

Produces pretty graphs in png files.
