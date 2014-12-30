#!/usr/bin/env python

"""An optimizing brainfuck-to-C compiler.

This program implements a couple of well known brainfuck optimizations
and compiles them them to C code. It is primarily written to enable
experimentation with different optimization combinations and to
illustrate how these optimizations function.

For a real, battle-tested compiler, we recommend awib:
http://code.google.com/p/awib/

Mats Linander <matslina (at) gmail (dot) com>
"""

import sys

from opt.cancel import opt_cancel
from opt.contract import opt_contract
from opt.clearloop import opt_clearloop
from opt.copyloop import opt_copyloop
from opt.multiloop import opt_multiloop
from opt.offsetops import opt_offsetops
from opt.scanloop import opt_scanloop
from opt.reorder import opt_reorder
from opt.ir import bf_to_ir, ir_to_c

opts = {'cancel': opt_cancel,
        'contract': opt_contract,
        'clearloop': opt_clearloop,
        'copyloop': opt_copyloop,
        'multiloop': opt_multiloop,
        'offsetops': opt_offsetops,
        'scanloop': opt_scanloop}

def main():
    ir = bf_to_ir(sys.stdin.read())

    optimizations = sys.argv[1:]
    if len(sys.argv) > 1 and sys.argv[1] == 'all':
        optimizations = ['clearloop', 'copyloop', 'multiloop',
                         'offsetops', 'contract', 'scanloop']

    for x in optimizations:
        if x == 'none':
            continue
        if x not in opts:
            sys.stderr.write("unknown optimization '%s'\n" % x)
            return 1
        ir = opts[x](ir)

    print ir_to_c(ir)

    return 0

if __name__ == '__main__':
    sys.exit(main())
