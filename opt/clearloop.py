from ir import *


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
