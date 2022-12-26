from re import sub
from pycparser import c_ast, CParser
import subprocess
import sys
import os
import json

from type import *
def resolv(node : Type, top : str, DECLS):
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
        if node.name != top and node.name in DECLS and DECLS[node.name] != node:
            node.resolves = DECLS[node.name]
        if node.name == top:
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
        l = l.replace("__builtin_va_list", "void").replace("__restrict", "").replace("__extension__", "").replace("__inline", "")
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

        if l[0] == "#":
            continue

        new_data.append(l)
    new_data = [l for l in new_data if not l.startswith("extern")]
    return "\n".join(new_data)


# UPDATE_CACHED_EVERY_N_HOURS = 2


def make_ast(source : str):
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

    for k, v in DECLS.items():
        print(k)
        t = parse_type(v)
        DECLS[k] = t
    return DECLS



CACHE_DIR =  os.path.join( os.path.dirname(__file__), "cache" )

def PULL_DECLS(headerfile : str):
    cache_path = os.path.join(CACHE_DIR, headerfile) + ".json"
    if os.path.exists(cache_path):
        f = open(cache_path, "r")
        data = json.load(f)
        f.close()
        return data
    else:
        clang = subprocess.Popen(("clang", "-E", "-", "-include"+headerfile), stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        source = clang.communicate(b"")[0].decode("utf8")
        source = cleanup_header(source)
        _global.SAUCE = source
        ast = make_ast(source)
        decls = extract_decls_from_ast(ast)
        
        decls_json = []
        for k, v in decls.items():
            resolv(v, k, decls)
            decls_json.append({
                "name" : k,
                "pretty_str" : str(v),
                "encoded_str" : v.encode()

            })

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        f = open(cache_path, "w")
        json.dump(decls_json, f)
        f.close()
        return decls_json



DEFAULT_HEADERS = [
    "stdio.h",
    "ctype.h",
    "sys/stat.h",
    "string.h",
    "math.h"
]


import _global
argv = sys.argv[:]
pretty = "-p" in argv

if pretty:
    idx = argv.index("-p")
    argv = argv[:idx] + argv[idx+1:]

if len(argv) < 2:
    print("Error: Expected a type name")
    exit(1)

typename = argv[1]
includes = argv[2:] if len(argv) > 2 else []
includes += DEFAULT_HEADERS

_global.init()
_global.INCLUDES = includes

DECLS = {}
for i in includes:
    decs = PULL_DECLS(i)
    for d in decs:
        DECLS[d["name"]] = d



if typename not in DECLS:
    print("Error: Failed to find type: " + typename)
    exit(1)

d = DECLS[typename]

if pretty:
    print(d["pretty_str"])
else:
    print(d["encoded_str"], end="")
