from multiloop import opt_multiloop


def opt_copyloop(ir):
    return opt_multiloop(ir, True)
