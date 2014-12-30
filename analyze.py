#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re


def loopstats(code):

    depth = 0
    pos = 0
    leaf = False
    nleaf = 0
    nrepos = 0

    for c in code:

        if c == '[':
            pos = 0
            leaf = True
            depth += 1

        elif c == ']':
            if leaf:
                nleaf += 1
                if pos != 0:
                    nrepos += 1
            leaf = False
            depth -= 1

        elif c == '>':
            pos += 1

        elif c == '<':
            pos -= 1

    return dict(nrepos=nrepos,
                nleaf=nleaf)


def main():
    code = ''.join([c for c in sys.stdin.read()
                    if c in (',' ,'.', '[', ']', '<', '>', '+', '-')])

    nall = len(code)
    nclearloops = 3 * (len(code.split('[-]')) - 1 + len(code.split('[+]')) - 1)
    nscanloops = 3 * (len(code.split('[>]')) - 1 + len(code.split('[<]')) - 1)
    ncontract = sum(map(len, re.findall(r'(\+{2,}|-{2,}|<{2,}|>{2,})', code)))
    nloops = len([c for c in code if c == '['])
    d = loopstats(code)

    print "clearloop", nclearloops, nall, "%.2f" % (float(nclearloops) / nall)
    print "scanloop", nscanloops, nall, "%.2f" % (float(nscanloops) / nall)
    print "contract", ncontract, nall, "%.2f" % (float(ncontract) / nall)
    print "reposloop", d['nrepos'], nloops, "%.2f" % (float(d['nrepos']) / nloops)
    print "leafloop", d['nleaf'], nloops, "%.2f" % (float(d['nleaf']) / nloops)

    return 0

if __name__ == "__main__":
    sys.exit(main())
