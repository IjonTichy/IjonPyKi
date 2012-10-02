#!/usr/bin/python3

import re
import os
import time
import string

BLOCKSEP_RE = re.compile("^ - ([a-zA-Z0-9\-_]+) -\s*$")
ALLOWEDCHARS = string.ascii_letters + string.digits + "_-." 

class Post(object):
    defQuote = {}

    def __init__(self, postid, fields=None, **kwargs):
        self.postid = postid

        if fields is None:
            self.__fields = {}
        else:
            self.__fields = fields
        
        self.__fields.update(kwargs)


        for item in self.__class__.defQuote:
            if item not in self:
                self[item] = self.__class__.defQuote[item]

    def get(self, field):
        if field in self.__fields:
            return self.__fields[field]
        else:
            return None

    # This only really works well with strings, ints, and floats :\
    @property
    def raw(self):
        return "> {}\n".format(self.postid) + self.rawNoHeader

    @property
    def rawNoHeader(self):
        ret = []
        blockVars = []

        for val in sorted(self):
            if self[val] is None:
                continue

            if "\n" in str(self[val]):
                blockVars.append(val)
            else:
                ret.append("{} = {}".format(val, self[val]))
        
        for val in blockVars:
            ret.append(" - {} - ".format(val))
            for line in self[val].splitlines():
                ret.append(line.replace("-", "&#45;"))

            ret.append(" - {} - ".format(val))

        return "\n".join(ret)

    @property
    def fields(self):
        return self.__fields

    @property
    def postid(self):
        return self.__postid

    @postid.setter
    def postid(self, val):
        if not isinstance(val, str):
            raise TypeError("postid must be str, not {}".format(val.__class__.__name__))

        for char in val:
            if char not in ALLOWEDCHARS:
                raise ValueError("\"{}\" is an invalid postid character".format(char))

        self.__postid = val

    def shortTitle(self, length=40):
        if 'title' not in self:
            return ""

        if len(self['title']) < length:
            return self['title']
        
        return self['title'][:length-3] + "..."

    def getTime(self):
        if 'posted' not in self:
            return "Stupid"

        try:
            posted = float(self['posted'])
        except ValueError:
            self['posted'] = "-1"
            posted = -1.0

        if posted == -1.0:
            return "Unknown"

        gmTime = time.localtime(posted)
        return time.strftime("%Y-%m-%d %H:%M", gmTime)

    def __repr__(self):
        return "_{}_".format(self.postid)

    def __iter__(self):
        return iter(self.__fields)

    def __getitem__(self, field):
        if field in self.__fields:
            return self.__fields[field]
        else:
            raise IndexError("\"{}\" not in {}".format(field, self.__class__.__name__))

    def __setitem__(self, field, val):
        
        if not isinstance(field, str):
            raise TypeError("\"{}\" (field) must be string".format(field))

        for char in field:
            if char not in ALLOWEDCHARS:
                raise TypeError("\"{}\" not allowed as field name".format(field))

        self.__fields[field] = val

    def __delitem__(self, field):
        if field in self.__fields:
            del self.__fields[field]
        else:
            raise IndexError("\"{}\" not in {}".format(field, self.__class__.__name__))


def parsePost(postid, postlines, retclass=Post):
    ret = retclass(postid)

    blockvar = None
    blockbuf = []
    blockmatch = None

    for line in postlines:
        line = line.rstrip()

        blockmatch = BLOCKSEP_RE.match(line)

        # handle the block delimiter, dump to var if necessary
        if blockmatch:
            # start block
            if blockvar is None:
                blockvar = blockmatch.group(1)
                continue

            # end block
            elif blockmatch.group(1) == blockvar:
                ret[blockvar] = "\n".join(blockbuf)
                blockbuf = []
                blockvar = None
                continue

        if blockvar:
            blockbuf.append(line)

        else:
            if not line:
                continue

            try:
                key, val = line.split(" = ", 1)
            except ValueError as e:
                raise ValueError("invalid post line: \"{}\"".format(line)) from e

            ret[key] = val

    if blockvar:
        raise SyntaxError("unclosed block: \"{}\"".format(blockvar))
    
    return ret
