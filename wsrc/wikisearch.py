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

        self.searchDB   = shelve.open(searchFile, writeback=True)

    def sync(self):
        self.searchDB.sync()

    def syncAll(self, debug=False):
        for curPage in self.searchDB:
            del self.searchDB[curPage]

        for page in os.listdir(self.pageDir):
            self.syncPage(page, noSync=True, debug=debug)

        self.sync()

    def syncPage(self, page, noSync=False, debug=False, revision=-1):
        self.searchDB[page] = {}

        wikiPage = wikipage.WikiPage(page)

        if not wikiPage.revisionList:
            del self.searchDB[page]
            return

        if revision == -1:
            revision = wikiPage.revisionList[0]

        ret = self.syncRevision(page, revision, debug)

        if None not in ret:
            newRev = {"words": ret[0], "links": ret[1]}
            self.searchDB[page][revision] = newRev
        else:
            del self.searchDB[page]

        if not noSync: self.sync()

    def syncRevision(self, page, revision=-1, debug=False):
        pagePath = self.pageDir + os.sep + page
        if not os.path.isdir(pagePath): return ret

        if revision == -1: revision = wikiPage.revisionList[0]

        wikiPage = wikipage.WikiPage(page)

        return syncPageObject(wikiPage, revision, debug)

    def syncPageObject(self, page, revision, debug=False, add=False):
        ret = (None, None)

        name = page.pageName
        pageWords = page.wordCounts(revision)
        pageLinks = page.getLinks(revision)['internal']

        if pageWords:
            ret = (pageWords, pageLinks)

            if debug:
                print("{} ({}):".format(page, revision))
                print("  w:", pageWords)
                print("  l:", pageLinks, "\n")

        if add and None not in ret:
            if name not in self.searchDB: self.searchDB[name] = {}
            newRev = {"words": ret[0], "links": ret[1]}
            self.searchDB[name][revision] = newRev


        return ret

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

    def search(self, query):
        pageRanks = collections.defaultdict(int)

        for page in self.searchDB:
            result = self.searchPage(query, page)
            pageRanks[page] += result[0]

            for i in result[1]:
                pageRanks[i] += result[1][i]

        ret = {}

        for rank in pageRanks:
            if pageRanks[rank] > 0:
                ret[rank] = pageRanks[rank]

        return ret

    def searchPage(self, query, page):
        if page not in self.searchDB: raise IndexError("no such page {}".format(page))

        revCount = len(self.searchDB[page])

        if revCount == 0:
            return [-0x7FFFFFFF, {}]
        
        ret = [0, collections.defaultdict(int)]

        for revision in self.searchDB[page]:
            result = self.searchRevision(query, page, revision)

            ret[0] += result[0]

            for linked in result[1]:
                ret[1][linked] += result[1][linked]

        ret[0] = int(ret[0] / revCount)
        for page in ret[1]: ret[1][page] = int(ret[1][page] / revCount)

        ret[1] = dict(ret[1])

        return ret

    def searchRevision(self, query, page, revision):
        page = page.lower()
        wikiPage = wikipage.WikiPage(page)
        nicename = wikiPage.niceName.lower()

        if revision not in self.searchDB[page]:
            raise IndexError("page {} has no revision {}".format(page, revision))

        rev = self.searchDB[page][revision]
        words = rev["words"]
        links = rev["links"]

        ret = [0, {}]

        query = query.lower()
        queryWords = wikipage.WORDRE.findall(query)

        for word in queryWords:
            if word in nicename:
                ret[0] += 10 * len(word)

            occurences = words.get(word, 0)
            ret[0] += occurences

        for link in links:
            linkNice = wikiPage.nicify(link)

            for word in linkNice.split():
                if word.lower() in queryWords:
                    ret[0] += 2 * len(word)

        if ret[0] > 0:
            for link in links:
                link = link.lower()
                ret[1][link] = ret[0] / 5

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
    def __init__(self, searchFile="deepSearchDB", pageDir="pages"):
        super().__init__(searchFile, pageDir)

    def syncPage(self, page, noSync=False, debug=False):
        self.searchDB[page] = {}

        wikiPage = wikipage.WikiPage(page)

        if not wikiPage.revisionList:
            del self.searchDB[page]
            return

        revisions = {}

        addedThings = False

        for rev in wikiPage.revisions:
            ret = self.syncRevision(page, rev, debug)

            if None not in ret:
                addedThings = True
                words = ret[0]
                links = ret[1]
            else:
                words = {}
                links = set()

            revisions[rev] = {"words": words, "links": links}

        if addedThings:
            self.searchDB[page].update(revisions)
        else:
            del self.searchDB[page]

        if not noSync: self.searchDB.sync()
