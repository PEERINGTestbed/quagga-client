#!/usr/bin/env python

'''Store and manipulate possible announcements from a prefix

This module provides two classes.  Both classes do not associate the
announcement with a prefix, as the announcement can be deployed on any
prefix.

The Announce class stores a prefix's announcement from a mux.  It can
be either WITHDRAWN or ANNOUNCED.  An Announce in the ANNOUNCED state
will be in one of the substates PREPENDED, NOPREPEND, and POISONED.
Manipulating an Announce in the WITHDRAWN or NOPREPEND states is
simple, as there is no other data involved.

Manipulating an Announce in the PREPENDED or POISONED state involves a
list of ASes that are prepended to the path.  In the PREPENDED status,
an Announce stores a list with one or more entries of HOMEASN (e.g.,
47065 47065 47065).  In the POISONED status, an Announce stores a list
of ASes or AS sets that terminate with HOMEASN (e.g., 704 6639 {73 88}
47065).  These lists do not include the instance of HOMEASN that is
automatically appended by the AS that receives the announcement.

The PrefixAnnounce class encapsulates the announcement of a whole
prefix; i.e., what each mux should announce.  The class is a wrapper
around a mapping of mux names to instances of Announce.  Among
interesting features are support for checking if two instances of
PrefixAnnounce are identical, and functions to dump (load) a
PrefixAnnounce to (from) a string.'''

HOMEASN = 47065
MAX_AS_SET_SIZE = 10

WITHDRAWN = 'withdrawn'
ANNOUNCED = 'announced'

NOPREPEND = 'noprepend'
PREPENDED = 'prepended'
POISONED = 'poisoned'


class Announce(object):#{{{
	def __init__(self, spec=WITHDRAWN):#{{{
		self.status = frozenset()
		self.prepend = tuple()
		self.poisoned = frozenset()
		self.__ilshift__(spec)
	#}}}

	def __ilshift__(self, spec):#{{{
		if spec == WITHDRAWN:
			self.status = frozenset([WITHDRAWN])
			self.prepend = None
			self.poisoned = set()
		elif spec == NOPREPEND:
			self.status = frozenset([ANNOUNCED, NOPREPEND])
			self.prepend = None
			self.poisoned = set()
		elif isinstance(spec, (str, unicode)):
			self.prepend = parse_as_path_string(spec)
			self._parse_update()
		elif isinstance(spec, (tuple, list)):
			self._parse_iter(spec)
			self._parse_update()
		else:
			raise RuntimeError('%s unsupported' % spec.__class__)
		return self
	#}}}

	def __str__(self):#{{{
		if WITHDRAWN in self.status:
			return WITHDRAWN
		elif NOPREPEND in self.status:
			return NOPREPEND
		else:
			return dump_as_path_tuple(self.prepend)
	#}}}

	def __hash__(self):#{{{
		return hash((self.status, self.prepend))
	#}}}

	def __eq__(self, other):#{{{
		return hash(self) == hash(other)
	#}}}

	def _parse_iter(self, iterable):#{{{
		self.prepend = tuple(_parse_single_token(t) for t in iterable)
	#}}}

	def _parse_update(self):#{{{
		assert self.prepend is not None and len(self.prepend) > 0
		if self.prepend[-1] != HOMEASN:
			self.prepend = tuple(list(self.prepend) + [HOMEASN])
		assert self.prepend[-1] == HOMEASN

		self.poisoned = set()
		for e in self.prepend:
			if e == HOMEASN:
				continue
			if isinstance(e, int):
				self.poisoned.add(e)
			elif isinstance(e, frozenset):
				assert len(e) <= MAX_AS_SET_SIZE
				self.poisoned.update(e)
			else:
				raise TypeError('%s unsupported' % e.__class__)
		self.poisoned = frozenset(self.poisoned)

		if self.poisoned:
			assert len(set(self.prepend)) > 1
			if self.prepend.count(HOMEASN) == 1:
				self.status = frozenset([ANNOUNCED, POISONED])
			else:
				self.status = frozenset([ANNOUNCED, POISONED, PREPENDED])
		else:
			assert set(self.prepend) == set([HOMEASN])
			self.status = frozenset([ANNOUNCED, PREPENDED])
	#}}}
#}}}


class PrefixAnnounce(dict):#{{{
	def __init__(self):#{{{
		super(PrefixAnnounce, self).__init__()
		self.identifier = None
	#}}}

	def __setitem__(self, mux, spec):#{{{
		if isinstance(spec, Announce):
			super(PrefixAnnounce, self).__setitem__(mux, spec)
		else:
			super(PrefixAnnounce, self).__setitem__(mux, Announce(spec))
	#}}}

	def __hash__(self):#{{{
		assert self.identifier is not None
		return hash(self.identifier)
	#}}}

	def __str__(self):#{{{
		return '; '.join('%s: %s' % (m, str(a))
				for m, a in self.items())
	#}}}

	def close(self):#{{{
		self.identifier = frozenset(self.items())
	#}}}

	def mux2str(self):#{{{
		return dict((mux, str(a)) for mux, a in self.items())
	#}}}

	@staticmethod
	def from_mux2str(mux2str):#{{{
		pfxa = PrefixAnnounce()
		for mux, string in mux2str.items():
			pfxa[mux] = Announce(string)
		pfxa.close()
		return pfxa
	#}}}

	@staticmethod
	def from_str(string):#{{{
		pfxa = PrefixAnnounce()
		for entry in string.split(';'):
			mux, prepstr = entry.split(':')
			mux = mux.strip()
			prepstr = prepstr.strip()
			pfxa[mux] = Announce(prepstr)
		pfxa.close()
		return pfxa
	#}}}
#}}}


def parse_as_path_string(string):#{{{
	prepend = list()
	string = string.replace(',', ' ')
	while '{' in string:
		head, _sep, string = string.partition('{')
		prepend.extend(_parse_single_token(t) for t in head.split())
		head, _sep, string = string.partition('}')
		asset = frozenset(_parse_single_token(t) for t in head.split())
		prepend.append(asset)
	prepend.extend(_parse_single_token(t) for t in string.split())
	return tuple(prepend)
#}}}

def dump_as_path_tuple(tup):#{{{
	tokens = list()
	for e in tup:
		if isinstance(e, int):
			tokens.append(str(e))
		elif isinstance(e, frozenset):
			tokens.append('{%s}' % ' '.join(str(i) for i in sorted(e)))
		else:
			raise TypeError('%s unsupported' % e.__class__)
	return ' '.join(tokens)
#}}}

def _parse_single_token(token):#{{{
	if isinstance(token, (str, unicode)):
		return int(token)
	if isinstance(token, int):
		return token
	if isinstance(token, (set, frozenset)):
		return frozenset(int(i) for i in token)
	raise TypeError('%s unsupported' % token.__class__)
#}}}


def test_announce():#{{{
	# pylint: disable=R0915
	a = Announce()
	assert WITHDRAWN in a.status
	assert len(a.status) == 1
	assert not a.prepend
	assert not a.poisoned
	assert str(a) == WITHDRAWN

	a <<= NOPREPEND
	assert ANNOUNCED in a.status
	assert NOPREPEND in a.status
	assert len(a.status) == 2
	assert not a.prepend
	assert not a.poisoned
	assert str(a) == NOPREPEND

	try:
		a <<= PREPENDED
	except ValueError:
		pass
	else:
		assert False

	try:
		a <<= POISONED
	except ValueError:
		pass
	else:
		assert False

	a <<= '47065 47065 47065'
	assert ANNOUNCED in a.status
	assert PREPENDED in a.status
	assert len(a.status) == 2
	assert len(a.prepend) == 3
	assert not a.poisoned

	b = Announce('47065,47065,47065')
	assert a == b

	c = Announce('47065, 47065 47065,47065')
	assert a != c
	assert ANNOUNCED in c.status
	assert PREPENDED in c.status
	assert len(c.status) == 2
	assert len(c.prepend) == 4
	assert not c.poisoned

	d = Announce('47065 47065 47065 47065')
	assert c == d

	e = Announce('704 {34,35 36} 47065')
	assert ANNOUNCED in e.status
	assert POISONED in e.status
	assert len(e.status) == 2
	assert len(e.prepend) == 3
	assert len(e.poisoned) == 4
	assert str(e) == '704 {34 35 36} 47065'

	f = Announce('704 {35 34 36} 47065')
	assert e == f
	assert str(f) == '704 {34 35 36} 47065'

	try:
		f <<= '704 {35 35 36}'
	except ValueError:
		pass
	else:
		assert False

	g = Announce('{704} {705} {45 46} 47065')
	assert ANNOUNCED in g.status
	assert POISONED in g.status
	assert len(g.status) == 2
	assert len(g.prepend) == 4
	assert len(g.poisoned) == 4
	assert str(g) == '{704} {705} {45 46} 47065'
#}}}


def test_prefix_announce():#{{{
	a = Announce('704 {34,35 36} 47065')

	pfxa = PrefixAnnounce()
	pfxa['wisc'] = a
	pfxa['gatech'] = a
	pfxa.close()
	s = str(pfxa)

	pfxb = PrefixAnnounce.from_str(s)
	assert pfxb == pfxa
#}}}


if __name__ == '__main__':
	test_announce()
	test_prefix_announce()







