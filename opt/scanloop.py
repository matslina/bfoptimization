from ir import *


def opt_scanloop(ir):

    out = ir[:2]

    for op in ir[2:]:
        if (op.__class__ == Close and
            out[-2].__class__ == Open and
            out[-1].__class__ in (Left, Right) and
            out[-1].x == 1):
            if out[-1].__class__ == Left:
                out.append(ScanLeft())
            else:
                out.append(ScanRight())
            assert out.pop(-2).__class__ in (Left,Right)
            assert out.pop(-2).__class__ == Open
        else:
            out.append(op)

    return out
