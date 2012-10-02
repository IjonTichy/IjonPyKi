#!/usr/bin/python3

import os, sys, shutil
import string, re
import time
import cgi

from . import post

# (?xi)
# \b
# (                           # Capture 1: entire matched URL
#   (?:
#     [a-z][\w-]+:                # URL protocol and colon
#     (?:
#       /{1,3}                        # 1-3 slashes
#       |                             #   or
#       [a-z0-9%]                     # Single letter or digit or '%'
#                                     # (Trying not to match e.g. "URI::Escape")
#     )
#     |                           #   or
#     www\d{0,3}[.]               # "www.", "www1.", "www2." … "www999."
#     |                           #   or
#     [a-z0-9.\-]+[.][a-z]{2,4}/  # looks like domain name followed by a slash
#   )
#   (?:                           # One or more:
#     [^\s()<>]+                      # Run of non-space, non-()<>
#     |                               #   or
#     \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
#   )+
#   (?:                           # End with:
#     \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
#     |                                   #   or
#     [^\s`!()\[\]{};:'".,<>?«»“”‘’]        # not a space or one of these punct chars
#   )
# )

URLRE = r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""

LINK1       = "<a href=\"?page={0}\">{1}</a>"
LINK2       = "<a href=\"{0}\" class=\"wikiExternal\">{1}</a>"

LETTERS     = string.ascii_letters
UPPER       = string.ascii_uppercase
LOWER       = string.ascii_lowercase
DIGITS      = string.digits
UPPERDIGITS = string.ascii_uppercase + string.digits
PUNCTUATION = "_-"
VALID       = LETTERS + DIGITS + PUNCTUATION
VALIDRE_0   = "[A-Z][a-z0-9_\-]+[A-Z][a-z0-9_\-]*"
VALIDRE_1   = "[A-Z][A-Z]+[a-z_\-][a-z0-9_\-]*"
VALIDRE     = "|".join((VALIDRE_0, VALIDRE_1))
VALIDRE2    = "(" + VALIDRE + ")"
VALIDRE3    = "([A-Za-z0-9_\-]+)"

INVALID     = "[^a-zA-Z0-9-_]"
INVALID2    = "([^a-zA-Z0-9-_])"

LINKRE      = re.compile("\\b" + VALIDRE2 + "\\b")
EXPLICITRE1 = re.compile("\[\[" + VALIDRE3 + "\]\]")
EXPLICITRE2 = re.compile("\[\[" + VALIDRE3 + " (.+?)\]\]")
EXPLICITRE3 = re.compile("\[\[" + URLRE + " (.+?)\]\]")

ITALICRE    = re.compile("'''(.+?)'''")
BOLDRE      = re.compile("''(.+?)''")

BRACECLASSRE= re.compile("\{\{([a-zA-Z]+):(.+?)\}\}")
NOLINKRE    = re.compile("^" + VALIDRE3 + "$")

SUBFORMATRE_PARTS = \
(
    "\[\[.+?\]\]",
    "\{\{.+?\}\}",
    "\\b" + VALIDRE + "\\b",
)

SUBFORMAT   = "({})".format(")|(".join(SUBFORMATRE_PARTS))
SUBFORMATRE = re.compile(SUBFORMAT)

CODESTART = "  "

class WikiFormatter(object):
    BraceClasses = {
        "image":        "<img src=\"{data[0]}\" />",
        "imageleft":    "<div class=\"floatLeft\"><img src=\"{data[0]}\" /></div>",
        "imageright":   "<div class=\"floatRight\"><img src=\"{data[0]}\" /></div>",
        "caption":      "<div class=\"wikiCaption\"><img src=\"{data[0]}\" /><br />{data[1]}</div>",
        "captionleft":  "<div class=\"floatLeft\"><img src=\"{data[0]}\" /><br />{data[1]}</div>",
        "captionright": "<div class=\"floatRight\"><img src=\"{data[0]}\" /><br />{data[1]}</div>",
    }
    
    def __init__(self):
        self.subformatters = (self.bracketFormat, self.braceFormat, self.linkFormat)
        self.braceClasses  = self.__class__.BraceClasses
    
    @staticmethod
    def nicify(title):
        def addchars(chars, char=None):
            nonlocal ret, lastChar
            ret += chars
            if char is None:    lastChar = chars
            else:               lastChar = char

        ret = ""
        lastChar = "A"

        for i in range(len(title)):
            lastChar    = "A" if (i == 0) else title[i-1]
            char        = title[i]
            nextChar    = "A" if (i == (len(title) - 1)) else title[i+1]

            if char in PUNCTUATION:
                if lastChar not in PUNCTUATION:
                    addchars(" " + char, char)
                    continue

            if char in UPPER:
                if lastChar not in UPPER:
                    addchars(" " + char, char)
                    continue

                if lastChar in UPPER and nextChar in LOWER:
                    addchars(" " + char, char)
                    continue

            if char in DIGITS:
                if lastChar in LOWER and nextChar in LOWER:
                    addchars(char)
                    continue

                if lastChar in LOWER:
                    addchars(" " + char, char)
                    continue

            addchars(char)
        
        return ret.strip()

    @staticmethod
    def unnicify(title):
        ret = []

        upperNext = True

        for char in title:
            if char in " \t":
                upperNext = True
                continue

            if upperNext:
                ret.append(char.upper())
                continue

            ret.append(char)

        return "".join(ret)

    def formatContents(self, contents, escaped=False):
        if not escaped:
            escapedLines = cgi.escape(contents)
            escapedLines = escapedLines.replace("&amp;#45;", "-")
        else:
            escapedLines = contents

        inCode = False
        lines = escapedLines.split("\n")
        ret = []
        
        for line in lines:
            retadd = ""

            if line.startswith(CODESTART):
                if not inCode:
                    retadd += "<div class=\"wikiSource\">"

                retadd += line[len(CODESTART):]
                inCode = True

            elif not line.strip():
                retadd = "\n"

            else:
                if inCode:
                    retadd += "</div>"

                inCode = False

                line2 = " " + line + " "
                line2 = SUBFORMATRE.sub(self.subformat, line2)
                line2 = ITALICRE.sub("<em>\g<1></em>", line2)
                line2 = BOLDRE.sub("<strong>\g<1></strong>", line2)
                retadd += line2[1:-1]
                retadd += "\n"

            ret.append(retadd)

        ret = "<br />".join(ret)

        if inCode:
            ret += "</div>"

        return ret

    def subformat(self, match):
        groups = match.groups()

        for func, group in zip(self.subformatters, groups):
            if group is not None:
                return func(group)
    
    def noFormat(self, group):
        return group

    def bracketFormat(self, group):
        explicit1 = EXPLICITRE1.match(group)
        explicit2 = EXPLICITRE2.match(group)
        explicit3 = EXPLICITRE3.match(group)
        
        if explicit1:
            groups = explicit1.groups()
            nice   = self.nicify(groups[0])
            return LINK1.format(groups[0], nice)

        if explicit2:
            groups = explicit2.groups()
            return LINK1.format(*groups[0:2])

        if explicit3:
            groups = explicit3.groups()
            return LINK2.format(groups[0], groups[-1])
        
        return " [[" + self.formatContents(group[2:-2], escaped=True).rstrip() + "]] "

    def braceFormat(self, group):
        noLink = NOLINKRE.match(group[2:-2])
        clsContents = BRACECLASSRE.match(group)

        if noLink:
            return group[2:-2]

        if clsContents:
            cls, contents = clsContents.groups()
            cls = cls.lower()

            contents  = [i.rstrip() for i in contents.split("|")]
            contents2 = [contents[0]]

            for i in contents[1:]:
                toAdd = self.formatContents(i, escaped=True)
                contents2.append(toAdd.rstrip())

            contents2 += ([""] * 10)   # ugly hack gooooooo

            formatDict = {"data": contents2}

            ret = self.braceClasses.get(cls, group).format(**formatDict)
            
            return ret
            

        return " {{" + self.formatContents(group[2:-2], escaped=True).rstrip() + "}} "

    def linkFormat(self, group):
        implicit = LINKRE.match(group)

        if implicit:
            link = implicit.group(1)
            return LINK1.format(link, self.nicify(link))
