from ir import *


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
