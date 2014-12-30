from ir import *


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
