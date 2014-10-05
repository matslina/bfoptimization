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
    opt = [ir[0]]
    for op in ir[1:]:
        if op[0] == opt[-1][0] and op[0] in ('add', 'sub', 'left', 'right'):
            opt[-1] = (opt[-1][0], (opt[-1][1][0] + op[1][0],))
        else:
            opt.append(op)
    return opt


def opt_clearloop(ir):
    opt = ir[:]
    i = 0
    while True:
        try:
            i = opt.index(('open', ()), i)
        except ValueError:
            break
        if (opt[i + 1][0] in ('add', 'sub') and
            opt[i + 1][1] == (1,) and
            opt[i + 2] == ('close', ())):
            opt = opt[:i] + [('clear', ())] + opt[i + 3:]
        i += 1
    return opt

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

    opt = ir[:]

    OFFSETABLE = ('add', 'sub', 'in', 'out', 'clear')
    BLOCKOPS = ('add', 'sub', 'in', 'out', 'clear', 'left', 'right')
    i = 0

    while i < len(opt):

        while i < len(opt) and opt[i][0] not in BLOCKOPS:
            i += 1
        if i >= len(opt):
            break

        j = i
        while j < len(opt) and opt[j][0] in BLOCKOPS:
#            print "move j past", opt[j], j
            j += 1

#        sys.stdout.write('%s %d %d %d\n' % (opt[i:j], i, j, len(opt)))

        block = []
        p = 0
        offset = {}
        for op in opt[i:j]:
            if op[0] == 'left':
                p -= op[1][0]
            elif op[0] == 'right':
                p += op[1][0]
            elif op[0] in ('out', 'in', 'clear'):
                block.extend( ('o' + x[0], (p,) + x[1]) for x in offset.get(p, []))
                block.append(('o' + op[0], (p,) + op[1]))
                offset[p] = []
            else:
                offset.setdefault(p, []).append(op)

        for off in sorted(offset):
            for op in offset[off]:
                if off:
                    block.append(('o' + op[0], (off,) + op[1]))
                else:
                    block.append(op)
        if p > 0:
            block.append(('right', (p,)))
        elif p < 0:
            block.append(('left', (-p,)))

        opt = opt[:i] + block + opt[j:]

#        print "block", block

#        print i,j
        i += len(block) + 1
#        print i,j

    return opt


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
