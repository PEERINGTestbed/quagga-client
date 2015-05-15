#!/usr/bin/python

import sys
import os

import resource
import time
import logging
import logging.handlers
import sqlite3
from optparse import OptionParser

import announce

HOMEASN = 47065
PREFIXES = range(236, 256)
MUX2IP = dict()


def poison(prefix, mux, poisonv, homeasn=HOMEASN): # {{{
    mux = mux.upper()
    assert mux in MUX2IP
    assert prefix in PREFIXES
    assert isinstance(poisonv, announce.Announce)
    assert isinstance(homeasn, int)
    # tstamp = int(time.time())
    # poison_string = str(poisonv)
    prepend_string = str(poisonv)
    # prepend_string = '%s %d' % (poison_string, homeasn)
    cmd = 'vtysh -d bgpd -c "config terminal" '
    cmd += '-c "route-map %s permit %d" ' % (mux, prefix)
    cmd += '-c "set as-path prepend %s"' % prepend_string
    reliable_exec(cmd, 3)
    _prefix_up(prefix, mux, prepend_string)
    # logging.info('ctrlpfx %d 184.164.%d.0/24 %s %s %s', tstamp,
    #       prefix, mux, 'announced', prepend_string)
# }}}


def unpoison(prefix, mux): # {{{
    mux = mux.upper()
    assert mux in MUX2IP, '%s %s' % (mux, MUX2IP)
    assert prefix in PREFIXES, '%s %s' % (prefix, PREFIXES)
    # tstamp = int(time.time())
    _reset_route_map(prefix, mux)
    _prefix_up(prefix, mux, 'noprepend')
    # logging.info('ctrlpfx %d 184.164.%d.0/24 %s %s %s', tstamp,
    #       prefix, mux, 'announced', 'no-prepend')
# }}}


def withdraw(prefix, mux): # {{{
    mux = mux.upper()
    assert mux in MUX2IP
    assert prefix in PREFIXES
    _reset_route_map(prefix, mux)
    # tstamp = int(time.time())
    logging.info('prefix down %d %s', prefix, mux)
    cmd = 'vtysh -d bgpd -c "config terminal" '
    cmd += '-c "route-map %s permit %d" ' % (mux, prefix)
    cmd += '-c "match ip address prefix-list NONET"'
    reliable_exec(cmd, 3)
    # logging.info('ctrlpfx %d 184.164.%d.0/24 %s %s %s', tstamp,
    #       prefix, mux, 'withdrawn', 'no-prepend')
# }}}


def soft_reset(mux): # {{{
    mux = mux.upper()
    assert mux in MUX2IP
    neighbor = MUX2IP[mux]
    # tstamp = int(time.time())
    # logging.info('soft_reset %s %s', mux, tstamp)
    cmd = 'vtysh -d bgpd -c "clear ip bgp %s soft out"' % neighbor
    reliable_exec(cmd, 3)
# }}}


def reliable_exec(cmd, maxerrors, wait_time=20): # {{{
    # logging.info(cmd)
    errors = 0
    r = os.system(cmd)
    while r != 0:
        errors += 1
        if errors > maxerrors:
            logging.info('tried running %s (%d times) but failed', cmd,
                    maxerrors)
            assert False
        time.sleep(wait_time)
        r = os.system(cmd)
# }}}


def deploy(prefix, pfxannounce):#{{{
    logging.info('deploying %s', str(pfxannounce))
    for mux, ace in pfxannounce.items():
        if announce.WITHDRAWN in ace.status:
            withdraw(prefix, mux)
        elif announce.NOPREPEND in ace.status:
            unpoison(prefix, mux)
        else:
            poison(prefix, mux, ace)
        soft_reset(mux)
#}}}


def load_mux2ip_from_database(filename):# {{{
    conn = sqlite3.connect(filename)
    curr = conn.cursor()
    result = curr.execute('select number, name from portal_server')
    for number, name in result:
        MUX2IP[name.upper()] = "10.%d.0.1" % (192 + number)
    conn.close()
# }}}


def _create_parser(): # {{{
    # pylint: disable=R0912

    def load_database(option, _optstr, value, parser): # {{{
        load_mux2ip_from_database(value)
        setattr(parser.values, option.dest, MUX2IP)
    # }}}
    def check_prefix(option, _optstr, value, parser): # {{{
        if value not in PREFIXES:
            sys.stderr.write('prefix %d out of allowed range:\n' % value)
            sys.stderr.write(' '.join(str(i) for i in PREFIXES) + '\n')
            sys.exit(1)
        setattr(parser.values, option.dest, value)
        pfx2mux = getattr(parser.values, 'pfx2mux')
        if pfx2mux is not None:
            setattr(parser.values, 'mux', pfx2mux[value])
    # }}}
    def check_mux(option, _optstr, value, parser): # {{{
        if getattr(parser.values, option.dest) is not None:
            sys.stderr.write('cannot have --mux and --pfx2mux,\n')
            sys.stderr.write('or multiple muxes specified\n')
            sys.exit(1)
        value = value.upper()
        if value == 'ALL':
            setattr(parser.values, option.dest, list(MUX2IP.keys()))
        elif value not in MUX2IP:
            sys.stderr.write('mux %s is unknown:\n' % value)
            sys.stderr.write(' '.join(MUX2IP.keys()) + '\n')
            sys.exit(1)
        else:
            setattr(parser.values, option.dest, [value])
    # }}}
    def set_operation(option, optstr, value, parser): # {{{
        if getattr(parser.values, option.dest) is not None:
            sys.stderr.write('duplicate operations, aborting.\n')
            sys.exit(1)
        if optstr == '--announce': optstr = '--unpoison'
        setattr(parser.values, option.dest, optstr)
        if optstr == '--poison':
            v = announce.Announce(value)
            setattr(parser.values, 'poison', v)
    # }}}
    def load_pfx2mux(option, _optstr, value, parser): # {{{
        if getattr(parser.values, 'mux') is not None:
            sys.stderr.write('cannot have --mux and --pfx2mux\n')
            sys.exit(1)
        pfx2mux = dict()
        fd = open(value, 'r')
        for line in fd:
            pfx, mux = line.split()
            pfx2mux[int(pfx)] = mux
        fd.close()
        setattr(parser.values, option.dest, pfx2mux)
        pfx = getattr(parser.values, 'prefix')
        if pfx is not None:
            setattr(parser.values, 'mux', pfx2mux[pfx])
    # }}}


    usage = 'usage: ctrlpfx.py --prefix=PREFIX --mux=NAME|--pfx2mux=FILE\n' +\
            '                  --poison=PREPEND|--unpoison|--withdraw|--unchanged'
    usage += ' [options]'
    parser = OptionParser(usage=usage)

    parser.add_option('--database',
            dest='database',
            metavar='DBFILE',
            action='callback',
            callback=load_database,
            nargs=1, type='str',
            help='database file')

    parser.add_option('--prefix',
            dest='prefix',
            metavar='PREFIX',
            action='callback',
            callback=check_prefix,
            nargs=1, type='int',
            help='3rd byte of prefix to control (e.g., 240)')

    parser.add_option('--mux',
            dest='muxes',
            metavar='NAME',
            action='callback',
            callback=check_mux,
            nargs=1, type='str',
            help='mux name to control (e.g., CLEMSON), or ALL')

    parser.add_option('--pfx2mux',
            dest='pfx2mux',
            metavar='FILE',
            action='callback',
            callback=load_pfx2mux,
            nargs=1, type='str',
            help='file with mapping from prefixes to muxes')

    parser.add_option('--poison',
            dest='op',
            metavar='PREPEND',
            action='callback',
            callback=set_operation,
            nargs=1, type='str',
            help='announce PREFIX poisoning PREPEND')

    parser.add_option('--unpoison',
            dest='op',
            action='callback',
            callback=set_operation,
            nargs=0,
            help='announce PREFIX unpoisoned (equivalent to --announce)')

    parser.add_option('--announce',
            dest='op',
            action='callback',
            callback=set_operation,
            nargs=0,
            help='announce PREFIX unpoisoned (equivalent to --unpoison)')

    parser.add_option('--withdraw',
            dest='op',
            action='callback',
            callback=set_operation,
            nargs=0,
            help='withdraw PREFIX')

    parser.add_option('--unchanged',
            dest='op',
            action='callback',
            callback=set_operation,
            nargs=0,
            help='keep announcement unchanged (useful to force soft-reset)')

    parser.add_option('--logfile',
            dest='logfile',
            metavar='FILE',
            default='log.txt',
            help='file to use for logging [default=%default]')

    parser.add_option('--bgprouter',
            dest='bgprouter',
            metavar='INT',
            type='int',
            default=47065,
            help='bgp router to configure through vtysh [default=%default]')

    parser.add_option('--homeasn',
            dest='homeasn',
            metavar='ASN',
            type='int',
            default=47065,
            help='prepend ASN to poisoned announcements [default=%default]')

    parser.add_option('--neighbor',
            dest='neighbor',
            metavar='IP',
            type='str',
            help='neighbor to use in the soft-reset [default=automatic]')

    parser.add_option('--no-soft-reset',
            dest='noreset',
            action='store_false',
            default=False,
            help='skip soft reset after config change [default=%default]')

    return parser
# }}}


def _prefix_up(prefix, mux, message): # {{{
    logging.info('prefix up %d %s %s', prefix, mux, message)
    cmd = 'vtysh -d bgpd -c "config terminal" '
    cmd += '-c "route-map %s permit %d" ' % (mux, prefix)
    cmd += '-c "match ip address prefix-list NET-%s"' % prefix
    reliable_exec(cmd, 3)
# }}}


def _reset_route_map(prefix, mux): # {{{
    # logging.info('resetting route-map %s permit %d', mux, prefix)
    cmd = 'vtysh -d bgpd -c "config terminal" '
    cmd += '-c "route-map %s permit %d" ' % (mux, prefix)
    cmd += '-c "set as-path prepend 1" '
    cmd += '-c "no set as-path prepend"'
    reliable_exec(cmd, 3)
# }}}


def _main(): # {{{
    parser = _create_parser()
    opts, _args = parser.parse_args()
    if opts.prefix is None or opts.op is None or opts.database is None:
        parser.parse_args(['-h'])

    resource.setrlimit(resource.RLIMIT_AS, (2147483648L, 2147483648L))

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    loghandler = logging.handlers.RotatingFileHandler(opts.logfile,
            maxBytes=128*1024*1024, backupCount=5)
    loghandler.setFormatter(formatter)
    logger.addHandler(loghandler)

    for mux in opts.muxes:
        if opts.op == '--poison':
            poison(opts.prefix, mux, opts.poison)
            if opts.noreset: continue
            soft_reset(mux)
        elif opts.op == '--unpoison':
            unpoison(opts.prefix, mux)
            if opts.noreset: continue
            soft_reset(mux)
        elif opts.op == '--withdraw':
            withdraw(opts.prefix, mux)
            if opts.noreset: continue
            soft_reset(mux)
        elif opts.op == '--unchanged':
            if opts.noreset:
                sys.stderr.write('--unchanged and --no-soft-reset do nothing')
                continue
            soft_reset(mux)
        else:
            sys.stderr.write('unknown operation, aborting.\n')
            sys.exit(1)

# }}}


if __name__ == '__main__':
    sys.exit(_main())
