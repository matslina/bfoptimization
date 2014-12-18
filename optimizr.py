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


def opt_cancel(ir):
    """Cancels out adjacent Add, Sub and Left Right.

    E.g., ++++-->>+-<<< is equivalent to +<.
    """

    opposite = {Add: Sub,
                Sub: Add,
                Left: Right,
                Right: Left}
    optimized = []

    for op in ir:
        if len(optimized) == 0:
            optimized.append(op)
            continue
        prev = optimized[-1]
        if prev.__class__ == opposite.get(op.__class__) and \
           getattr(prev, 'offset', 0) == getattr(op, 'offset', 0):
            x = prev.x - op.x
            if x < 0:
                optimized[-1] = op._replace(x=-x)
            elif x > 0:
                optimized[-1] = prev._replace(x=x)
            else:
                optimized.pop(-1)
        else:
            optimized.append(op)

    return optimized


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
    """Replaces copy and multiplication loops with Copy and Mul.

    The copy loop is a common construct in brainfuck, where something
    like [->>+>+<<<] is used to duplicate the current cell to two
    other cells. This example can be replaced with three constant time
    operations: Copy(2) Copy(3) Clear(0).

    The multiplication loop is similar but adds a multiplicative
    factor to the value being copied. E.g. [->>+++++>++<<<] can be
    replaced with Mul(2, 5) Mul(3, 2) Clear(0).
    """

    ir = ir[:]

    i = 0
    while True:

        # find the next "leaf loop", i.e. the next loop that doesn't
        # hold any other loops. break if no such loop exists.
        while i < len(ir):
            if isinstance(ir[i], Open):
                break
            i += 1
        else:
            break
        j = i + 1
        while j < len(ir):
            if isinstance(ir[j], Close):
                break
            if isinstance(ir[j], Open):
                i = j
            j += 1
        else:
            break

        # verify that the loop only holds arithmetic and pointer
        # operations.
        if set(op.__class__ for op in ir[i + 1:j]) - \
           set([Add, Sub, Left, Right]) != set():
            i = j
            continue

        # interpret the loop and track pointer position and what
        # arithmetic operations it carries out
        mem, p = {}, 0
        for op in ir[i + 1:j]:
            if isinstance(op, Add):
                mem[p + op.offset] = mem.get(p, 0) + op.x
            elif isinstance(op, Sub):
                mem[p + op.offset] = mem.get(p, 0) - op.x
            elif isinstance(op, Right):
                p += op.x
            elif isinstance(op, Left):
                p -= op.x

        # if pointer ended up where it started (cell 0) and we
        # subtracted exactly 1 from cell 0, then this loop can be
        # replaced with a Mul instruction
        if p != 0 or mem.get(0, 0) != -1:
            i = j
            continue
        mem.pop(0)

        # the copyloop optimization only handles the case of copying
        # cells without a multiplicative factor. e.g., [->>+>+<<<] is
        # a copy loop while [->>+>+++<<<] is a multiplication loop,
        # since the latter adds the current cell's value times 3 to
        # the third cell.
        if onlycopy and set(mem.values() + [1]) != set([1]):
            i = j
            continue

        # all systems go: replace the loop with Mul or Copy operations
        optblock = [Copy(p) if onlycopy else Mul(p, mem[p])
                    for p in mem]
        ir = ir[:i] + optblock + [Clear(0)] + ir[j + 1:]
        i += len(optblock) + 2

    return ir


def opt_offsetops(ir, reorder=False):
    """Adds offsets to operations where applicable.

    Pointer positioning, i.e. < and > or Left and Right, can often be
    eliminated by providing offsets to other instructions. E.g.,
    ->>>++.>>->> becomes Add(2, 3) Out(3) Sub(1, 5) Right(7).

    This implementation will produce 7 consecutive Right(1) instead of
    a single Right(7) though. This is so to allow this optimization to
    be evaluated in isolation, without it also implementing
    contraction of Left/Right. Take care to run contract *after*
    offsetops if you're applying both.
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
        optblock, offset, order, p = [], {}, [], 0
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
                if not offset.get(p, []):
                    offset[p] = []
                offset[p].append(op)
                order.append(p)

        # then dump the remaining arithmetic operations
        if reorder:
            order.sort()
            if len([x for x in order if x < p]) > len(order) / 2:
                order = list(reversed(order))
        for off in order:
            optblock.extend(op._replace(offset=off) for op in offset[off])
            offset[off] = []

        # and finally reposition the pointer to wherever it ended up
        if p > 0:
            optblock.extend([Right(1) for _ in range(p)])
        elif p < 0:
            optblock.extend([Left(1) for _ in range(-p)])

        # replace the code block with the optimized block
        ir = ir[:i] + optblock + ir[j:]
        i += len(optblock) + 1

    return ir


def opt_reorder(ir):
    return opt_offsetops(ir, reorder=True)


opts = {'cancel': opt_cancel,
        'contract': opt_contract,
        'clearloop': opt_clearloop,
        'copyloop': opt_copyloop,
        'multiloop': opt_multiloop,
        'offsetops': opt_offsetops,
        'reorder': opt_reorder}

def main():
    ir = bf_to_ir(sys.stdin.read())

    optimizations = sys.argv[1:]
    if len(sys.argv) > 1 and sys.argv[1] == 'all':
        optimizations = ['clearloop', 'copyloop', 'multiloop',
                         'offsetops', 'contract']

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
