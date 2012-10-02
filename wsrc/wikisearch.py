#!/usr/bin/env python3

import sys, os
import collections
import shelve
import cgi

from . import wikipage

HTMLTEMPLATE = """\
<div class="wikiSearch">
  <div class="searchHead">Results for {query}</div>
  <ul class="searchResults">
{result}
  </ul>
</div>"""

SEARCHTEMPLATE = """    <li class="searchResult"><a href="?page={page}">{title}</a> (relevance: {relevance})</li>"""

NORESULTS = """No results for "{query}" found."""

class WikiSearcher(object):
    def __init__(self, searchFile="wikiSearchDB", pageDir="pages"):
        self.searchFile = os.path.abspath(searchFile)
        self.pageDir    = os.path.abspath(pageDir)

        if not os.path.isdir(self.pageDir):
            raise IOError("\"{}\" is not a directory".format(pageDir))

        self.searchDB   = shelve.open(searchFile)

    def syncAll(self, printStatus=False):
        for page in os.listdir(self.pageDir):
            self.syncPage(page, noSync=True)

            if printStatus:
                print("updating search DB for {}".format(page))

        self.searchDB.sync()

    def syncPage(self, page, noSync=False):
        pagePath = self.pageDir + os.sep + page

        if not os.path.isdir(pagePath): return

        wikiPage = wikipage.WikiPage(page)
        pageWords = wikiPage.wordCounts()

        if pageWords:
            self.searchDB[page] = pageWords
        elif page in self.searchDB:
            del self.searchDB[page]

        if not noSync: self.searchDB.sync()

    def search(self, query):
        ret = collections.defaultdict(int)
        query = query.lower()

        for page in self.searchDB:
            tmp = self.searchPage(query, page)
            if tmp: ret[page] = tmp

        return dict(ret)

    def searchPage(self, query, page):
        ret = 0
        pageWords = self.searchDB[page]

        query = query.lower()

        for word in wikipage.WORDRE.findall(query):
            if word in page: ret += 2*len(word)

            ret += pageWords.get(word, 0)
        
        return ret

    def searchHTML(self, query, rCount=-1, rStart=0):
        results = self.search(query)
        rSorted = list(sorted(results, reverse=True, key=(lambda x: results[x])) )

        resultsPage = []
        retDict = {"query": query}
        formatDict = {}

        if rCount == -1:
            rEnd = len(rSorted)
        else:
            rEnd += rStart

        if not rSorted:
            formatDict['query'] = cgi.escape(query)

            resultsPage = [NORESULTS.format(**formatDict)]
        
        elif rStart >= len(rSorted):
            resultsPage = ["No results found past this point."]

        for result in rSorted[rStart:rEnd]:
            page = wikipage.WikiPage(result)

            formatDict['relevance'] = results[result]
            formatDict['page']      = cgi.escape(result)
            formatDict['title']     = cgi.escape(page.displayTitle)

            resultsPage.append(SEARCHTEMPLATE.format(**formatDict))

        ret = "\n".join(resultsPage)

        retDict["result"] = ret

        return HTMLTEMPLATE.format(**retDict)

    def __del__(self):
        self.searchDB.sync()


class WikiSearcherDeep(WikiSearcher):
    def syncPage(self, page, noSync=False):
        pagePath = self.pageDir + os.sep + page

        if not os.path.isdir(pagePath): return

        revisions = {}

        wikiPage = wikipage.WikiPage(page)

        for rev in wikiPage.revisions:
            revisions[rev] = wikiPage.wordCounts(rev)
        
        if revisions:
            self.searchDB[page] = revisions

        if not noSync: self.searchDB.sync()

    def searchPage(self, query, page):
        ret = 0
        revisions = self.searchDB[page]

        query = query.lower()

        for word in wikipage.WORDRE.findall(query):
            if word in page: ret += 2*len(word)

            for revision in revisions:
                revWords = revisions[revision]
                ret += revWords.get(word, 0)
        
        return ret
