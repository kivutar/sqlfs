#!/usr/bin/env python 

import sys
import copy
import time
import getopt
import getpass
import os
from os.path import basename

import py9p
import MySQLdb

class MySQLfs(py9p.Server):
    """
    A local filesystem device.
    """

    files={}
    def __init__(self):
        self.dotu = 0
        self.cancreate = 0
        self.root = py9p.Dir(0)
        self.root.qid = py9p.Qid(py9p.QTDIR, 0, py9p.hash8('/'))
        self.root.localpath = '/'
        self.root.children = []
        self.files[self.root.qid.path] = self.root
        for db in self.myexec("show databases"):
            self.root.children.append(db[0])
    
    def myexec(self, cmd):
        db = MySQLdb.connect("localhost", "root", "root", "koha")
        cursor = db.cursor()
        cursor.execute(cmd)
        ret = cursor.fetchall()
        db.close()
        return ret

    def getfile(self, path):
        if not self.files.has_key(path):
            return None
        return self.files[path]

    def pathtodir(self, f):
        '''Stat-to-dir conversion'''
        s = []
        if f in self.myexec("show databases"):
            type = py9p.QTDIR
            res = py9p.DMDIR
        else:
            type = py9p.QTFILE
            res = 0770
        qid = py9p.Qid(type, 0, py9p.hash8(f))
        return py9p.Dir(1, 0, type, qid,
                res,
                0, 0,
                0, basename(f), 0, 0, 0)

#    def open(self, srv, req):
#        f = self.getfile(req.fid.qid.path)
#        if not f:
#            srv.respond(req, "unknown file")
#            return
#        if (req.ifcall.mode & 3) == py9p.OWRITE:
#            if not self.cancreate:
#                srv.respond(req, "read-only file server")
#                return
#            if req.ifcall.mode & py9p.OTRUNC:
#                m = "wb"
#            else:
#                m = "r+b"        # almost
#        elif (req.ifcall.mode & 3) == py9p.ORDWR:
#            if not self.cancreate:
#                srv.respond(req, "read-only file server")
#                return
#            if m & OTRUNC:
#                m = "w+b"
#            else:
#                m = "r+b"
#        else:                # py9p.OREAD and otherwise
#            m = "rb"
#        if not (f.qid.type & py9p.QTDIR):
#            f.fd = _os(file, f.localpath, m)
#        srv.respond(req, None)

    def walk(self, srv, req):
        f = self.getfile(req.fid.qid.path)
        if not f:
            srv.respond(req, 'unknown file')
            return
        npath = f.localpath
        for path in req.ifcall.wname:
            # normpath takes care to remove '.' and '..', turn '//' into '/'
            npath = os.path.normpath(npath + "/" + path)
            if len(npath) <= len(self.root.localpath):
                # don't let us go beyond the original root
                npath = self.root.localpath

            if path == '.' or path == '':
                req.ofcall.wqid.append(f.qid)
            elif path == '..':
                # .. resolves to the parent, cycles at /
                qid = f.parent.qid
                req.ofcall.wqid.append(qid)
                f = f.parent
            else:
                d = self.pathtodir(npath)
                nf = self.getfile(d.qid.path)
                if nf:
                    # already exists, just append to req
                    req.ofcall.wqid.append(d.qid)
                    f = nf
                elif npath == '/':                   # /
                    print "affiche les databases"
                    req.ofcall.wqid.append(f.qid)
                elif len(npath[1:].split('/')) == 1: # /database
                    print "les tables"
                    req.ofcall.wqid.append(f.qid)
                elif len(npath[1:].split('/')) == 2: # /database/table
                    print "les entries"
                    req.ofcall.wqid.append(f.qid)
                elif len(npath[1:].split('/')) == 3: # /database/table/entry
                    print "c'est un fichier"
                    d.localpath = npath
                    d.parent = f
                    self.files[d.qid.path] = d
                    req.ofcall.wqid.append(d.qid)
                    f = d                    
                else:
                    srv.respond(req, "can't find %s"%path)
                    return

        req.ofcall.nwqid = len(req.ofcall.wqid)
        srv.respond(req, None)

#    def remove(self, srv, req):
#        f = self.getfile(req.fid.qid.path)
#        if not f:
#            srv.respond(req, 'unknown file')
#            return
#        if not self.cancreate:
#            srv.respond(req, "read-only file server")
#            return
#
#        if f.qid.type & py9p.QTDIR:
#            _os(os.rmdir, f.localpath)
#        else:
#            _os(os.remove, f.localpath)
#        self.files[req.fid.qid.path] = None
#        srv.respond(req, None)
#
#    def create(self, srv, req):
#        fd = None
#        if not self.cancreate:
#            srv.respond(req, "read-only file server")
#            return
#        if req.ifcall.name == '.' or req.ifcall.name == '..':
#            srv.respond(req, "illegal file name")
#            return
#
#        f = self.getfile(req.fid.qid.path)
#        if not f:
#            srv.respond(req, 'unknown file')
#            return
#        name = f.localpath+'/'+req.ifcall.name
#        if req.ifcall.perm & py9p.DMDIR:
#            perm = req.ifcall.perm & (~0777 | (f.mode & 0777))
#            _os(os.mkdir, name, req.ifcall.perm & ~(py9p.DMDIR))
#        else:
#            perm = req.ifcall.perm & (~0666 | (f.mode & 0666))
#            _os(file, name, "w+").close()
#            _os(os.chmod, name, perm)
#            if (req.ifcall.mode & 3) == py9p.OWRITE:
#                if req.ifcall.mode & py9p.OTRUNC:
#                    m = "wb"
#                else:
#                    m = "r+b"        # almost
#            elif (req.ifcall.mode & 3) == py9p.ORDWR:
#                if m & OTRUNC:
#                    m = "w+b"
#                else:
#                    m = "r+b"
#            else:                # py9p.OREAD and otherwise
#                m = "rb"
#            fd = _os(open, name, m)
#
#        d = self.pathtodir(name)
#        d.parent = f
#        self.files[d.qid.path] = d
#        self.files[d.qid.path].localpath = name
#        if fd:
#            self.files[d.qid.path].fd = fd
#        req.ofcall.qid = d.qid
#        srv.respond(req, None)

    def clunk(self, srv, req):
        f = self.getfile(req.fid.qid.path)
        if not f:
            srv.respond(req, 'unknown file')
            return
        f = self.files[req.fid.qid.path]        
        if hasattr(f, 'fd') and f.fd is not None:
            f.fd.close()
            f.fd = None
        srv.respond(req, None)

    def stat(self, srv, req):
        f = self.getfile(req.fid.qid.path)
        if not f:
            srv.respond(req, "unknown file")
            return
        req.ofcall.stat.append(self.pathtodir(f.localpath))
        srv.respond(req, None)

    def read(self, srv, req):
        f = self.getfile(req.fid.qid.path)
        if not f:
            srv.respond(req, "unknown file")
            return

        if f.qid.type & py9p.QTDIR:
            req.ofcall.stat = []
            for x in f.children:
                req.ofcall.stat.append(x)
        else:
            result = self.myexec("SELECT * FROM %s WHERE id=%s" % (f.parent, f))
            buf = str( result )
            if req.ifcall.offset > len(buf):
                req.ofcall.data = ''
            else:
                req.ofcall.data = buf[req.ifcall.offset : req.ifcall.offset + req.ifcall.count]
        srv.respond(req, None)

#    def write(self, srv, req):
#        if not self.cancreate:
#            srv.respond(req, "read-only file server")
#            return
#
#        f = self.getfile(req.fid.qid.path)
#        if not f:
#            srv.respond(req, "unknown file")
#            return
#
#        f.fd.seek(req.ifcall.offset)
#        f.fd.write(req.ifcall.data)
#        req.ofcall.count = len(req.ifcall.data)
#        srv.respond(req, None)

def usage(prog):
    print >>sys.stderr, "usage:  %s [-dcD] [-p port] [-r root] [-l listen] [-a authmode] [srvuser domain]" % prog
    sys.exit(1)

def main():
    import getopt
    import getpass

    prog = sys.argv[0]
    args = sys.argv[1:]

    port = py9p.PORT
    listen = '0.0.0.0'
    root = '/'
    mods = []
    user = None
    noauth = 0
    chatty = 0
    cancreate = 0
    dotu = 0
    authmode = None
    dom = None
    passwd = None
    key = None

    try:
        opt,args = getopt.getopt(args, "dDcp:r:l:a:")
    except:
        usage(prog)
    for opt,optarg in opt:
        if opt == "-D":
            chatty = 1
        if opt == "-d":
            dotu = 1
        if opt == '-c':
            cancreate = 1
        if opt == '-r':
            root = optarg
        if opt == "-p":
            port = int(optarg)
        if opt == '-l':
            listen = optarg
        if opt == '-a':
            authmode = optarg

    if authmode == 'sk1':
        if len(args) != 2:
            print >>sys.stderr, 'missing user and authsrv'
            usage(prog)
        else:
            py9p.sk1 = __import__("py9p.sk1").sk1
            user = args[0]
            dom = args[1]
            passwd = getpass.getpass()
            key = py9p.sk1.makeKey(passwd)
    elif authmode == 'pki':
        py9p.pki = __import__("py9p.pki").pki
        user = 'admin'
    elif authmode != None and authmode != 'none':
        print >>sys.stderr, "unknown auth type: %s; accepted: pki, sk1, none"%authmode
        sys.exit(1)

    srv = py9p.Server(listen=(listen, port), authmode=authmode, user=user, dom=dom, key=key, chatty=chatty, dotu=dotu)
    srv.mount(MySQLfs())
    srv.serve()

#'''
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "interrupted."
'''
if __name__ == "__main__":
    import trace

    # create a Trace object, telling it what to ignore, and whether to
    # do tracing or line-counting or both.
    tracer = trace.Trace(
        ignoredirs=[sys.prefix, sys.exec_prefix],
        trace=1,
        count=1)

    # run the new command using the given tracer
    tracer.run('main()')
    # make a report, placing output in /tmp
    r = tracer.results()
    r.write_results(show_missing=True, coverdir="/tmp")
#'''

