from pycparser import parse_file, c_ast, CParser
import subprocess
import sys
import os
import tempfile
DEFAULT_HEADERS = [
    "stdio.h",
    "ctype.h",
    "sys/stat.h"
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

include_args = [ f"-include{h}" for h in includes ]

empty = subprocess.Popen(("echo", ""), stdout=subprocess.PIPE)
result = subprocess.Popen(("clang", "-E", "-", *include_args), stdin=empty.stdout, stdout=subprocess.PIPE)
result.wait()
data = "\n".join([l.decode("utf8") for l in result.stdout]).splitlines()
new_data = []
next = None
# Sanitize the input file so pycparser does not get mad
for l in data:
    if "\n" in l: 
        d = l.split("\n")
        for m in d:
            data.append(m)
        continue
    if next:
        l = next + l
        next = None
    l = l.replace("__builtin_va_list", "void").replace("__restrict", "")
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

    # print(">", l)
    new_data.append(l)


new_data = [l for l in new_data if not l.startswith("extern")]

new_file = "\n".join(new_data)
data = new_file

_global.SAUCE = data
# print(data)
# exit()
parser = CParser()
ast = parser.parse(data, filename="<none>")
from type import *

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

    t = parse_type(v)
    DECLS[k] = t

def resolv(node : Type, top : str):
    for m in dir(node):
        a = getattr(node, m)
        if isinstance(a, Type): resolv(a, top)
        if type(a) == dict:
            for v in a.values():
                if not isinstance(v, Type): continue
                # print("resol dict key")
                resolv(v, top)

    if isinstance(node, Named):
        if node.name == top: return
        node.resolves = DECLS[node.name]
    if isinstance(node, Opaque):
        if node.name != top and node.name in DECLS and DECLS[node.name] != node:
            node.resolves = DECLS[node.name]
        if node.name == top:
            node.resolves = Primitive("self", 0, True)

for k, d in DECLS.items():
    if isinstance(d, Opaque):
        entry = DECLS[d.name]
        if entry == d:
            continue
        DECLS[k] = DECLS[d.name]

    resolv(d, k)

d = DECLS[typename]

if pretty:
    print(d)
else:
    print(d.encode(), end="")
