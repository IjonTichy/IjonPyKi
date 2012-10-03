#!/usr/bin/python3

import sys, os, string
import cgi, cgitb

if __name__ == "__main__": cgitb.enable()

from wsrc import wikipage, wikisearch, post

def getPage(args):
    inner = title = ""

    try:
        page  = wikipage.WikiPage(args["page"], tryUnnicify=True)
        inner = page.getHTML(args["rev"], args["source"])
        title = page.niceName

    except ValueError:
        inner = "Invalid page name \"{0}\".".format(args["page"])
        title = "Invalid page"
    
    return {"inner": inner, "title": title}

def addPage(args):
    inner = title = ""
    revNum = 0

    try:
        newRev = post.Post("irrelevant", fields={"page": args["text"]})
        page   = wikipage.WikiPage(args["page"])
        revNum = page.addRevision(newRev)
        search = wikisearch.WikiSearcher()
        search.syncPageObject(page, revNum, add=True)
        search.sync()

    except KeyError as e:
        inner = "Tried to get key \"{0}\", failed.".format(e.args[0])
        title = "KeyError"

    except ValueError:
        inner = "Invalid page name \"{0}\".".format(args["page"])
        title = "Invalid page"

    args["rev"] = revNum

    if inner: return {"inner": inner, "title": title}
    else: return getPage(args)

def searchPage(args):
    inner = title = ""

    if "q" not in args:
        inner = "No query specified. (\"q\" parameter)"
        title = "Search - <none>"
    else:
        query = args["q"]
        searcher = wikisearch.WikiSearcher()
        inner = searcher.searchHTML(query)
        title = "Search - \"{}\"".format(query)

    return {"inner": inner, "title": title}

modes = {
    "get": getPage,
    "add": addPage,
    "search": searchPage
}

if __name__ == "__main__":
    pageDict = {}; args = {}

    form = cgi.FieldStorage()
    for i in form: args[i] = form[i].value
    del form

    if "page" not in args: args["page"] = "MainPage"
    if "source" not in args: args["source"] = 0
    if "rev" not in args: args["rev"] = -1
    if "mode" not in args: args["mode"] = "get"

    pageName = cgi.escape(args["page"])

    try: args["source"] = int(args["source"])
    except ValueError: args["source"] = False

    try: args["rev"] = int(args["rev"])
    except ValueError: args["rev"] = False

    if "q" in args: args["mode"] = "search"

    if args["mode"] not in modes:
        mode = modes["get"]
    else:
        mode = modes[args["mode"]]

    pageDict.update(mode(args))

    page = open("wiki.html").read()
    pageTemplate = string.Template(page)

    print("Content-type: text/html\n")
    print(pageTemplate.safe_substitute(pageDict))
