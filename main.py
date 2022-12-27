from ctypes import addressof
from datetime import datetime
import subprocess
import sys
import os
import json
import _global

import sqlite3

con = sqlite3.connect("cache.db")
cur = con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS headers(name STRING PRIMARY KEY, last_update DATE NOT NULL)")
cur.execute("""CREATE TABLE IF NOT EXISTS dependencies(
    base STRING NOT NULL,
    targets STRING NOT NULL,
    FOREIGN KEY(base) REFERENCES headers(name),
    FOREIGN KEY(targets) REFERENCES headers(name)
    )""")
cur.execute("""CREATE TABLE IF NOT EXISTS declarations(
    name STRING PRIMARY KEY,
    header STRING NOT NULL,
    pretty_str STRING NOT NULL,
    encode_str STRING NOT NULL,
    FOREIGN KEY(header) REFERENCES headers(name)
    )""")

con.commit()

def resolv(node, top : str, DECLS):
    from type import Type, Named, Opaque, Primitive
    # print(addressof(node))
    for m in dir(node):
        a = getattr(node, m)
        if isinstance(a, Type): resolv(a, top, DECLS)
        if type(a) == dict:
            for v in a.values():
                if not isinstance(v, Type): continue
                # print("resol dict key")
                resolv(v, top, DECLS)

    if isinstance(node, Named):
        if node.name == top: return
        node.resolves = DECLS[node.name]
    if isinstance(node, Opaque):
        if node.name in DECLS and DECLS[node.name] == node:
            pass
        elif node.name != top and node.name in DECLS:
            node.resolves = DECLS[node.name]
        elif node.name == top:
            node.resolves = Primitive("self", 0, True)



def cleanup_header(src : str) -> str:
    src = src.replace("\n\n", "\n")
    data = src.splitlines()
    new_data = []
    next = None
    for l in data:
        if "\n" in l: 
            d = l.split("\n")
            for m in d:
                data.append(m)
            continue
        if next:
            l = next + l
            next = None
        l = l.replace("__builtin_va_list", "void").replace("__restrict", "").replace("__extension__", "").replace("__inline", "").replace("__signed__", "signed")
        l = l.strip()
    
        if "__attribute__" in l:
            attr_idx = l.index("__attribute__")
            l = l[:attr_idx] + ";"
        if "__asm__" in l:
            asm_idx = l.index("__asm__")
            l = l[:asm_idx] + ";"
        if l == "" or l.isspace(): continue
        if l == ";":
            new_data[-1]+=";"
            continue

        if l.endswith(","):
            next = l
            continue

        # if l[0] == "#":
            # continue

        new_data.append(l)
    new_data = [l for l in new_data if not l.startswith("extern")]
    return "\n".join(new_data)


# UPDATE_CACHED_EVERY_N_HOURS = 2


def make_ast(source : str):
    from pycparser import CParser
    parser = CParser()

    ast = None
    try:
        ast = parser.parse(source, filename="<none>")
    except Exception as e:
        print(source)
        print("Bug: Pycparser exception")
        print(e)
        exit(1)
    return ast

def extract_decls_from_ast(ast):
    DECLS = {}
    from pycparser import c_ast
    from type import parse_type
    class DeclVisitor(c_ast.NodeVisitor):
        def visit_Typedef(self, node):
            if node.name in DECLS: return
            DECLS[node.name] = node.type
        def visit_Struct(self, node):
            # print(node.name)
            if node.name in DECLS: 
                if DECLS[node.name].decls is not None:
                    return
            DECLS[node.name] = node

    DeclVisitor().visit(ast)

    cnt = {}
    for k, v in DECLS.items():
        if not k in cnt: cnt[k] = 0
        cnt[k] += 1
        t = parse_type(v)
        t.pos = str(v.coord).split(":")[0]
        DECLS[k] = t
    return DECLS




def assert_headers_exist(headers):
    # print(headers)
    result = cur.execute("SELECT 1 FROM headers WHERE name = ?", [headers])
    data = result.fetchall()
    # print(data)

def assert_header_entry_exists(header : str):
    args = [ header ]
    result = cur.execute("SELECT 1 FROM headers WHERE name = ?", args).fetchone()
    if result: return True

    # Build dependencies
    output = subprocess.Popen(("cc", "-H", header, "-o", ".tmp"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output.wait()
    deps = output.stderr.read().decode("utf8")
    deps = [l[2:].strip() for l in deps.splitlines() if l.startswith(". ")]

    # Create a new header
    # print("made ", header)
    res = cur.execute("INSERT INTO headers(name, last_update) VALUES (?, ?)", [header, datetime.now()])

    # Create deps
    for dep in deps:
        res = cur.execute("INSERT INTO dependencies(base, targets) VALUES (?, ?)", [header, dep])
    con.commit()

def mkdcl(headerfile : str):
        clang = subprocess.Popen(("clang", "-E", "-", "-include"+headerfile), stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        source = clang.communicate(b"")[0].decode("utf8")
        source = cleanup_header(source)
        _global.SAUCE = source
        ast = make_ast(source)
        decls = extract_decls_from_ast(ast)

        from type import Opaque

        DCS = {}
        for k, v in decls.items():
            resolv(v, k, decls)
            if not v.pos in DCS:
                # print("--------")
                DCS[v.pos] = []

            # print(v.pos, k)
            OBJ = {
                "name" : k,
                "pretty_str" : str(v),
                "encode_str" : v.encode()
            }
            # print(OBJ)
            DCS[v.pos].append(OBJ)

        RET = []

        for k in DCS.keys():
            already_exists = assert_header_entry_exists(k)

            # print("HEADER: " + k)
            if already_exists: 
                # print(">>> EXISTS")
                continue
            # name, header, pretty_str, encode_str
            EXEC = []
            for value in DCS[k]:
                name = value["name"]
                # print(name)
                pretty = value["pretty_str"]
                encode = value["encode_str"]
                EXEC.append(( name, k, pretty, encode ))
                RET.append(value)
                pass
            result = cur.executemany("INSERT OR REPLACE into declarations(name, header, pretty_str, encode_str) VALUES (?, ?, ?, ?)", EXEC)
        con.commit()
def BATCH_CREATE_DECL(headerfiles):
    assert_headers_exist(headerfiles)
    pass

def CREATE_DECL(headerfile : str):
        exists = assert_header_entry_exists(headerfile)
        if exists: return
        mkdcl(headerfile)



def GET_DECL(name : str):
    res = cur.execute("SELECT * FROM declarations WHERE name = ?", [name])
    data = res.fetchone()
    if not data: return None
    return {
        "pretty" : data[2],
        "encode" : data[3]
    }

