#!/usr/bin/python3

import os, sys, shutil
import collections
import string, re
import time
import cgi

from . import post, wikiformat

TIMEFORMAT  = "%Y-%m-%d_%H:%M:%S"
TIMEFORMAT2 = "%Y-%m-%d %H:%M:%S"

SOURCE      = "<textarea readonly=\"1\" class=\"source\">{0}</textarea>"
REVLINK     = "<a href=\"?page={0};rev={1}\">{2}</a>"
REVLINK_SRC = "<a href=\"?page={0};rev={1};source=1\">{2}</a>"

LETTERS     = string.ascii_letters
UPPER       = string.ascii_uppercase
LOWER       = string.ascii_lowercase
DIGITS      = string.digits
UPPERDIGITS = string.ascii_uppercase + string.digits
PUNCTUATION = "_-"
VALID       = LETTERS + DIGITS + PUNCTUATION

NOTAGRE     = re.compile("<[^<]+?>")
WORDRE      = re.compile("([a-zA-Z0-9]+(?:'[a-zA-Z0-9]*)?)")

inner = open("wikiInner.html").read()
inner = string.Template(inner)

addInner = open("wikiAdd.html").read()
addInner = string.Template(addInner)


class WikiPage(object):
    def __init__(self, pagename, postdir="pages/", *, tryUnnicify=False):

        postdir = os.path.abspath(postdir)

        self.formatter  = wikiformat.WikiFormatter()
        self.revisions  = {}

        if not os.path.isdir(postdir): raise IOError("{0} is not a directory".format(postdir))

        if not self.validTitle(pagename) and tryUnnicify:
            pagename = self.formatter.unnicify(pagename)

        if not self.validTitle(pagename):
            raise ValueError("\"{0}\" is an invalid name for a Wiki page".format(pagename))

        self.title      = pagename[0].upper() + pagename[1:]
        self.pageName   = self.title.lower()
        self.postDir    = postdir + os.sep + self.pageName
        self.metaFile   = self.postDir + os.sep + "metadata.txt"

        if not os.path.isdir(self.postDir):
            if os.path.exists(self.postDir):
                raise IOError("{0} exists and is not a directory".format(self.postDir))
            else:
                os.mkdir(self.postDir)

        self.updateMetadata()
        self.updateRevisions()

    @staticmethod
    def validTitle(pagename):
        if not pagename: return False

        for char in pagename:
            if char not in VALID: return False

        return True

    def nicify(self, name):
        return self.formatter.nicify(name)

    def unnicify(self, name):
        return self.formatter.unnicify(name)
    
    @property
    def niceName(self):
        return self.formatter.nicify(self.title)

    @property
    def displayTitle(self):
        return self.metadata.get("title", self.niceName)

    @property
    def revisionList(self):
        return list(sorted(self.revisions, reverse=True))

    def getMetadata(self):
        if not os.path.isfile(self.metaFile):
            return None

        metaLines = open(self.metaFile).read().splitlines()
        metadataPost = post.parsePost("metadata", metaLines)

        return metadataPost
        
    def commitMetadata(self):
        metaCommit = post.Post("metadata")

        for val in self.metadata:
            metaCommit[val] = self.metadata[val]
        
        open(self.metaFile, "w").write(metaCommit.rawNoHeader + "\n")

    def updateMetadata(self):
        self.metadata = {}
        meta = self.getMetadata()

        if meta:
            for val in meta:
                self.metadata[val] = meta[val]
        else:
            self.metadata["title"] = self.niceName
            self.commitMetadata()

    def updateRevisions(self):
        self.revisions = {}

        for revision in os.listdir(self.postDir):
            absRev = self.postDir + os.sep + revision

            try:
                revTime = revision.split(".")[0]
                revTime = time.strptime(revTime, TIMEFORMAT)
                revTime = int(time.mktime(revTime))
            except ValueError:
                continue

            revLines = open(absRev).read().splitlines()

            try:
                self.revisions[revTime] = post.parsePost(str(revTime), revLines)
            except (ValueError, SyntaxError):
                newRev = list(absRev.partition("."))
                newRev[0] += "~"
                newRev = "".join(newRev)

                shutil.move(absRev, newRev)   # make the check fail from now on
                continue

        return len(self.revisions)

    def purgeOldest(self, cutoff=50):
        for revision in self.revisionList[cutoff:]:
            fileTime = time.gmtime(revision)
            fileTime = time.strftime(TIMEFORMAT, fileTime)

            os.remove(self.postDir + os.sep + fileTime + ".txt")

    def addRevision(self, newRevision):
        curTime = time.strftime(TIMEFORMAT, time.gmtime())

        newRev = open(self.postDir + os.sep + curTime + ".txt", "w")
        newRev.write(newRevision.rawNoHeader)
        newRev.close()

        self.updateRevisions()
        self.purgeOldest()

        return self.revisionList[0]

    def revisionListHTML(self, current=-1, source=False):
        if not self.revisions: return "None"
        if current < 0: current = self.revisionList[0]

        if source:
            formatStr = REVLINK_SRC
        else:
            formatStr = REVLINK

        ret = []

        for i, revision in enumerate(self.revisionList):
            if current == revision:
                ret.append("{0}".format(time.strftime(TIMEFORMAT2, time.gmtime(revision)) ) )
            else:
                ret.append(formatStr.format(self.title, revision,
                                          time.strftime(TIMEFORMAT2, time.gmtime(revision))
                                         )
                          )

        return "<br />\n".join(ret)

    def get(self, revision=-1):
        if not self.revisions: return None
        if revision not in self.revisions:
            revision = self.revisionList[0]

        wanted = self.revisions[revision]

        if "page" in wanted:
            return wanted
        else:
            raise TypeError("revision \"{0}\" does not have page data".format(revision))

    def getPage(self, revision=-1):
        page = self.get(revision)

        if not page: return ""

        return page["page"]
    
    def getLinks(self, revision=-1):
        page = self.getPage(revision)
        parsed, links = self.formatter.formatContents(page, withLinks=True)

        return links

    def getHTML(self, revision=-1, source=False, *, onlyContents=False):
        formatDict = {}
        formatDict["page"]  = self.title
        formatDict["title"] = self.displayTitle

        if not self.revisions:
            if onlyContents:
                return ""

            contents    = "\"{0}\" is empty - fix that.".format(self.displayTitle)
            revision    = "What revision?"
            revisions   = "None"
            sourcename  = "Create {0}".format(self.displayTitle)
            sourcelink  = "?page={0};source=1".format(self.title, revision)
        else:

            if revision not in self.revisions: revision = self.revisionList[0]

            contents    = self.getPage(revision)
            revisions   = self.revisionListHTML(revision, source)

            if source:
                sourcename  = "Back to {0}".format(self.displayTitle)
                sourcelink  = "?page={0};rev={1}".format(self.title, revision)

            else:
                contents = self.formatter.formatContents(contents)
                sourcename  = "Edit {0} here".format(self.displayTitle)
                sourcelink  = "?page={0};rev={1};source=1".format(self.title, revision)

        if onlyContents:
            return contents

        formatDict["content"]       = contents
        formatDict["revision"]      = revision
        formatDict["revisions"]     = revisions
        formatDict["sourceLink"]    = sourcelink
        formatDict["sourceName"]    = sourcename
        
        if source:
            return addInner.safe_substitute(formatDict)
        else:
            return inner.safe_substitute(formatDict)

    def wordCounts(self, revision=-1):
        pageCrap = NOTAGRE.sub("", self.getHTML(revision, onlyContents=True))
        pageCrap = pageCrap.lower()

        ret = collections.defaultdict(int)

        for word in pageCrap.split():
            per = set()

            word = WORDRE.search(word)
            if not word: continue
            word = word.group(1).lower()

            ret[word] += 1
            continue

            for i in range(len(word)):
                for j in range(i+1, len(word)+1):
                    per |= {word[i:j]}

            for i in per:
                ret[i] += 1

        return dict(ret)
