# Quagga announcement controller

Scripts to control announcements from the Quagga software router.
This is the *old* set of scripts used by [PEERING][1] clients to
control announcements.  We keep this repository available as it may
be of use to experimenters using Quagga.  Unless you specifically
need Quagga, we recommend the new [BIRD-based client][2].

  [1]: http://peering.usc.edu
  [2]: https://github.com/PEERINGTestbed/client


```
Usage: ctrlpfx.py --mux2ip=FILE --prefix=PREFIX --mux=NAME|--pfx2mux=FILE
                  --poison=PREPEND|--unpoison|--withdraw|--unchanged [options]

Options:
  -h, --help        show this help message and exit
  --mux2ip=DBFILE   file mapping muxes to IPs
  --prefix=PREFIX   3rd byte of prefix to control (e.g., 240)
  --mux=NAME        mux name to control (e.g., CLEMSON), or ALL
  --pfx2mux=FILE    file with mapping from prefixes to muxes
  --poison=PREPEND  announce PREFIX poisoning PREPEND
  --unpoison        announce PREFIX unpoisoned (equivalent to --announce)
  --announce        announce PREFIX unpoisoned (equivalent to --unpoison)
  --withdraw        withdraw PREFIX
  --unchanged       keep announcement unchanged (useful to force soft-reset)
  --logfile=FILE    log to a file [default=stderr]
  --debuglog        log more information (useful for debugging)
  --bgprouter=INT   bgp router to configure through vtysh [default=47065]
  --homeasn=ASN     prepend ASN to poisoned announcements [default=47065]
  --neighbor=IP     neighbor to use in the soft-reset [default=automatic]
  --no-soft-reset   skip soft reset after config change [default=False]
```
