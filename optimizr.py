#!/usr/bin/env python

import sys
from collections import namedtuple


# The IR

# These map directly to the 8 regular brainfuck instructions. The
# exception is the offset parameter, which would be 0 in regular
# brainfuck, but can here indicate an offset from the current cell at
# which the operation should be applied.
Add = namedtuple('Add', ['x', 'offset'])
Sub = namedtuple('Sub', ['x', 'offset'])
Right = namedtuple('Right', ['x'])
Left = namedtuple('Left', ['x'])
In = namedtuple('In', ['offset'])
Out = namedtuple('Out', ['offset'])
Open = namedtuple('Open', [])
Close = namedtuple('Close', [])

# This IR has a couple of additional operations. Clear sets a cell to
# 0. Copy copies the current cell to 'off' positions away. Mul is like
# Copy but also holds a factor to multiply the copied value with.
Clear = namedtuple('Clear', ['offset'])
Copy = namedtuple('Copy', ['off'])
Mul = namedtuple('Mul', ['off', 'factor'])


def bf_to_ir(brainfuck):
    """Translates brainfuck to IR."""

    simplemap = {'+': Add(1, 0),
                 '-': Sub(1, 0),
                 '>': Right(1),
                 '<': Left(1),
                 ',': In(0),
                 '.': Out(0),
                 '[': Open(),
                 ']': Close()}

    return [simplemap[c] for c in brainfuck if c in simplemap]


def ir_to_c(ir):
    """Translates IR into a C program."""

    plain = {Add: 'mem[p] += %(x)d;',
             Sub: 'mem[p] -= %(x)d;',
             Right: 'p += %(x)d;',
             Left: 'p -= %(x)d;',
             Open: 'while (mem[p]) {',
             Close: '}',
             In: 'mem[p] = getchar();',
             Out: 'putchar(mem[p]);',
             Clear: 'mem[p] = 0;',
             Copy: 'mem[p+%(off)d] += mem[p];',
             Mul: 'mem[p+%(off)d] += mem[p] * %(factor)d;'}

    woff = {Add: 'mem[p+%(offset)d] += %(x)d;',
            Sub: 'mem[p+%(offset)d] -= %(x)d;',
            In: 'mem[p+%(offset)d] = getchar();',
            Out: 'putchar(mem[p+%(offset)d]);',
            Clear: 'mem[p+%(offset)d] = 0;'}

    code = [(woff if getattr(op, 'offset', 0) else plain)[op.__class__] % op._asdict()
            for op in ir]
    code.insert(0, '\n'.join(['#include <stdio.h>',
                              'unsigned char mem[65536];',
                              'int main() {',
                              'int p=0;']))
    code.append('return 0;')
    code.append('}')

    return '\n'.join(code)


def opt_contract(ir):
    """Contracts multiple Add, Sub, Left and Right into single instructions.

    Some brainfuck instructions can be contracted into single
    instructions. E.g., the brainfuck '>>>+++<<<---' can be contracted
    into 4 IR instructions: Right(3), Add(3), Left(3), Sub(3).
    """

    optimized = [ir[0]]

    for op in ir[1:]:
        prev = optimized[-1]
        if (op.__class__ in (Add, Sub, Left, Right) and
            op.__class__ == prev.__class__ and
            getattr(op, 'offset', 0) == getattr(prev, 'offset', 0)):
            # op is contractable, of same type and with same offset
            # (if any) as the previous opt
            optimized[-1] = prev._replace(x = prev.x + op.x)
        else:
            optimized.append(op)

    return optimized


def opt_clearloop(ir):
    """Replaces clear loops ([-] and [+]) with single instructions."""

    optimized = []

    for op in ir:
        optimized.append(op)
        if (op.__class__ == Close and
            len(optimized) > 2 and
            optimized[-2].__class__ in (Sub, Add) and
            optimized[-2].x == 1 and
            optimized[-2].offset == 0 and
            optimized[-3].__class__ == Open):
            # last 3 ops are [-] or [+] so replace with Clear
            optimized.pop(-1)
            optimized.pop(-1)
            optimized[-1] = Clear(0)

    return optimized


def opt_copyloop(ir):
    return opt_multiloop(ir, True)


def opt_multiloop(ir, onlycopy=False):
    opt = ir[:]
    i = -1
    while True:
        try:
            i = opt.index(('open', ()), i + 1)
            j = opt.index(('close', ()), i)
        except ValueError:
            break

#        sys.stderr.write("%s " % set([op[0] for op in opt[i + 1:j]]))
        if set() != \
           set([op[0] for op in opt[i + 1:j]]) - \
           set(['add', 'sub', 'left', 'right']):
#            sys.stderr.write("niet\n")
            continue

        mem = {}
        p = 0
        for op in opt[i + 1:j]:
            if op[0] == 'add':
                mem[p] = mem.get(p, 0) + op[1][0]
            elif op[0] == 'sub':
                mem[p] = mem.get(p, 0) - op[1][0]
            elif op[0] == 'left':
                p -= op[1][0]
            elif op[0] == 'right':
                p += op[1][0]

        if p != 0:
#            sys.stderr.write("pointer return fail\n")
            i = j
            continue

        if mem.get(0, 0) != -1:
#            sys.stderr.write("-1 fail\n")
            i = j
            continue
        mem.pop(0)

        if onlycopy and set(mem.values() + [1]) != set([1]):
#            sys.stderr.write("plain copy fail\n")
            i = j
            continue

        opt = (opt[:i] +
               [('copy' if onlycopy else 'mul', (off, mem[off]))
                for off in mem] +
               [('clear', ())] +
               opt[j + 1:])
        i += len(mem) + 1

    return opt

def opt_offsetops(ir):
    """Adds offsets to operations where applicable.


    Pointer positioning, i.e. < and > or Left and Right, can often be
    eliminated by providing offsets to other instructions. E.g.,
    ->>>++.>>->> becomes Add(2, 3) Out(3) Sub(1, 5) Right(7).
    """

    ir = ir[:]

    i = 0
    while i < len(ir):

        # find the next block of "offsetable" instructions
        BLOCKOPS = (Add, Sub, Left, Right, Clear, In, Out)
        while i < len(ir) and ir[i].__class__ not in BLOCKOPS:
            i += 1
        if i >= len(ir):
            break
        j = i
        while j < len(ir) and ir[j].__class__ in BLOCKOPS:
            j += 1

        # interpret the block and track what arithmetic operations are
        # applied to each offset. as soon as a non-arithmetic
        # operation is encountered, we dump the arithmetic operations
        # performed on that offset followed by the non-arithmetic
        # operation.
        optblock, offset, p = [], {}, 0
        for op in ir[i:j]:
            if isinstance(op, Left):
                p -= op.x
            elif isinstance(op, Right):
                p += op.x
            elif op.__class__ in (Out, In, Clear):
                optblock.extend(x._replace(offset=p) for x in offset.get(p, []))
                optblock.append(op._replace(offset=p))
                offset[p] = []
            else:
                offset.setdefault(p, []).append(op)

        # then dump the remaining arithmetic operations
        for off in sorted(offset):
            optblock.extend(op._replace(offset=off) for op in offset[off])

        # and finally reposition the pointer to wherever it ended up
        if p > 0:
            optblock.append(Right(p))
        elif p < 0:
            optblock.append(Left(-p))

        # replace the code block with the optimized block
        ir = ir[:i] + optblock + ir[j:]
        i += len(optblock) + 1

    return ir


opts = {'contract': opt_contract,
        'clearloop': opt_clearloop,
        'copyloop': opt_copyloop,
        'multiloop': opt_multiloop,
        'offsetops': opt_offsetops}

def main():
    ir = bf_to_ir(sys.stdin.read())

    if len(sys.argv) > 1 and sys.argv[1] == 'all':
        sys.argv = sys.argv[:0] + sorted(opts.keys())

    for x in sys.argv[1:]:
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
