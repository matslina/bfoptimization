from ir import *


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
