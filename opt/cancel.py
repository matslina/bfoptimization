from ir import *


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
