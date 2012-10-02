#!/usr/bin/env python3

import sys
from wsrc import wikisearch

searcher = wikisearch.WikiSearcher()

if len(sys.argv) > 1:
    print(searcher.searchHTML(" ".join(sys.argv[1:])))
else:
    searcher.syncAll(True)
