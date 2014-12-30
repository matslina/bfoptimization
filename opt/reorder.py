import offsetops


def opt_reorder(ir):
    return offsetops.opt_offsetops(ir, reorder=True)
