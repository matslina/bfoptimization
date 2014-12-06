#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re

def main():
    code = ''.join([c for c in sys.stdin.read()
                    if c in (',' ,'.', '[', ']', '<', '>', '+', '-')])

    ncloops = 3 * (len(code.split('[-]')) - 1 + len(code.split('[+]')) - 1)
    ncontract = sum(map(len, re.findall(r'(\+{2,}|-{2,}|<{2,}|>{2,})', code)))
    nall = len(code)

    print "clearloop", ncloops, nall, "%.2f" % (float(ncloops) / nall)
    print "contract", ncontract, nall, "%.2f" % (float(ncontract) / nall)

    return 0

if __name__ == "__main__":
    sys.exit(main())
