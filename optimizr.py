#!/usr/bin/env python

import sys

C_HEADER = '''
#include <stdio.h>
#include <time.h>
unsigned char mem[65536];
int main() {
int p=0;
clock_t time_start, time_stop;
time_start = clock();
'''

C_FOOTER = '''
time_stop = clock();
fprintf(stderr, "%.2f\\n",
        ((double)(time_stop - time_start))/CLOCKS_PER_SEC);
return 0;
}
'''


def bf_to_ir(bf):
    ir = []

    for c in bf:
        if c == '+':
            ir.append(('add', (1,)))
        elif c == '-':
            ir.append(('sub', (1,)))
        elif c == '>':
            ir.append(('right', (1,)))
        elif c == '<':
            ir.append(('left', (1,)))
        elif c == '[':
            ir.append(('open', ()))
        elif c == ']':
            ir.append(('close', ()))
        elif c == '.':
            ir.append(('out', ()))
        elif c == ',':
            ir.append(('in', ()))

    return ir

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

        p = 0
        offset = {}
        for op in opt[i:j]:
            if op[0] == 'left':
                p -= op[1][0]
            elif op[0] == 'right':
                p += op[1][0]
            else:
                offset.setdefault(p, []).append(op)

        block = []
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


def ir_to_c(ir):
    map = {'add': 'mem[p] += %d;',
           'sub': 'mem[p] -= %d;',
           'right': 'p += %d;',
           'left': 'p -= %d;',
           'open': 'while (mem[p]) {',
           'close': '}',
           'in': 'mem[p] = getchar();',
           'out': 'putchar(mem[p]);',
           'clear': 'mem[p] = 0;',
           'copy': 'mem[p+%d] += mem[p]; // * %d;',
           'mul': 'mem[p+%d] += mem[p] * %d;',
           'oadd': 'mem[p+%d] += %d;',
           'osub': 'mem[p+%d] -= %d;',
           'oin': 'mem[p+%d] = getchar();',
           'oout': 'putchar(mem[p+%d]);',
           'oclear': 'mem[p+%d] = 0;'}

    code = []
    try:
        code.extend([map[op] % arg for op, arg in ir])
    except KeyError:
        raise Exception('foobar failure: %s' % op)

    code.insert(0, C_HEADER)
    code.append(C_FOOTER)

    return '\n'.join(code)


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
