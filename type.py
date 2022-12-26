from ctypes import *
from execute import eval_c_expr
import _global
def get_bit(i : int, n : int):
    return (i >> (n*8)) & 0xff

def i2s(i : int):
    b1 = chr(get_bit(i, 0))
    b2 = chr(get_bit(i, 1))
    b3 = chr(get_bit(i, 2))
    b4 = chr(get_bit(i, 3))

    return f"{b4}{b3}{b2}{b1}"

class Type: pass



class Opaque(Type):
    name : str
    def __init__(self, name):
        self.name = name
        self.resolves = None
    def __repr__(self):
        return "opaque."+self.name if not self.resolves else str(self.resolves)
    def size(self):
        return -1;

    def encode(self):
        if self.resolves: return self.resolves.encode()
        return "o"

class Ptr(Type):
    def __init__(self, of):
        self.of = of
    def __repr__(self):
        return str(self.of)+"*"
    def size(self):
        return sizeof(c_void_p)
    def encode(self):
        return "p"+self.of.encode()
class List(Type):
    def __init__(self, of, siz : int):
        self.of = of
        self.size = siz

    def __repr__(self):
        return f"{self.of}[{self.size}]"
    def size(self):
        return self.of.size() * self.size


    def encode(self):
        return f"a{i2s(self.size)}{self.of.encode()}"

class Struct(Type):
    def __init__(self, members):
        self.members = members
    def size(self):
        tot = 0
        for m in self.members.values(): tot += m.size() 
        return tot
    def __repr__(self):
        ret = "struct{\n"
        for k, m in self.members.items():
            s = str(m).replace("\n", "\n\t")
            ret += f"\t{k} : {s},\n"
        return ret + "}"

    def encode(self):
        ret = "S" + i2s(len(self.members))
        # for each member:
        # name0x0type|
        for n, t in self.members.items():
            ret += n
            ret += chr(0)
            ret += t.encode()
            ret +="|"
        if len(self.members): ret = ret[:-1]
        return ret


class Union(Type):
    def __init__(self, members):
        self.members = members
    def size(self):
        bg = 0
        for m in self.members.values():
            s = m.size()
            if s > bg: bg = s
        return bg
    def __repr__(self):
        return "enum\n\t" + ", \n\t".join([ f"{k} : {v}" for k, v in self.members.items() ])
    def encode(self):
        ret = "U" + i2s(len(self.members))
        # for each member:
        # name0x0type|
        for n, t in self.members.items():
            ret += n
            ret += chr(0)
            ret += t.encode()
            ret +="|"
        if len(self.members): ret = ret[:-1]
        return ret
class Primitive(Type):
    def __init__(self, name, mod, signed):
        self.mod = mod
        self.name = name
        self.signed = signed

    def __repr__(self):
        ret = "" if self.signed else "unsigned "
        if self.mod > 0: 
            for i in range(self.mod): ret+="long "
        if self.mod < 0: 
            for i in range(-self.mod): ret+="short "
        return ret + self.name
    def size(self):
        raise Exception("cannot get size of " + str(self))
    def encode(self):
        if self.name == "char": return "i"+i2s(8) if self.signed else "u"+i2s(8)
        if self.name == "int":
            p = "i" if self.signed else "u"
            t = c_int if self.mod == 0 else c_long if self.mod == 1 else c_longlong if self.mod == 2 else c_short if self.mod == -1 else None
            if not t: raise Exception("Unhandled primitive int: " + str(self))
            return f"{p}{i2s(sizeof(t)*8)}"
        if self.name == "void": return "v"
        if self.name == "bool": return "b"
        if self.name == "int128": return "i"+i2s(128)
        if self.name == "float":
            t = c_float if self.mod == 0 else None
            return f"f{i2s(sizeof(t)*8)}"
        if self.name == "double":
            t = c_double if self.mod == 0 else c_longdouble if self.mod == 1 else None
            return f"f{i2s(sizeof(t)*8)}"
        if self.name == "self": return "s"
        raise Exception("Unhandled primitive: " + str(self))
class Named(Type):
    def __init__(self, name):
        self.name = name
        self.resolves = None

    def __repr__(self):
        return str(self.resolves) if self.resolves is not None else self.name
    def encode(self):
        return self.resolves.encode()
from pycparser import c_ast

def parse_struct(node : c_ast.Struct):
    if node.decls == None:
        return Opaque(node.name)
    else:
        decs = {}
        for d in node.decls:
            dname = d.name
            dtype = d.type
            typ = parse_type(dtype)
            decs[dname] = typ
        return Struct(decs)

PSTR = [
    "int", "bool", "float", "double", "char", "__int128", "void",
    "short", "long", "unsigned", "signed"
]


def parse_type(node : c_ast.Node):
    if isinstance(node, c_ast.TypeDecl): return parse_type(node.type)
    if isinstance(node, c_ast.PtrDecl): return Ptr(parse_type(node.type))
    if isinstance(node, c_ast.Struct): return parse_struct(node)
    if isinstance(node, c_ast.IdentifierType):
        names = node.names
        if not names[0] in PSTR: 
            assert(len(names) == 1)
            return Named(names[0])
        signed = True
       
        mod = 0
        while len(names) > 1 and (names[0] == "long" or names[0] == "short" or names[0] == "unsigned" or names[0] == "signed"):
            if names[0] == "long": mod+=1
            elif names[0] == "short": mod-=1
            elif names[0] == "unsigned": signed = False
            names = names[1:]

        assert(len(names) == 1)
        ty = names[0]
        if ty == "char": return Primitive("char", 0, signed)
        elif ty == "int": return Primitive("int", mod, signed)
        elif ty == "short": return Primitive("int", mod-1, signed)
        elif ty == "long": return Primitive("int", mod+1, signed)
        elif ty == "double": return Primitive("double", mod, True)
        elif ty == "float": return Primitive("float", mod, True)
        elif ty == "bool": return Primitive("bool", 0, False)
        elif ty == "__int128": return Primitive("int128", mod, signed)
        elif ty == "void": return Primitive("void", mod, signed)
        raise Exception("Unimplemented Primitive: " + ty)

    if isinstance(node, c_ast.ArrayDecl):
        members = parse_type(node.type)
        if node.dim is None: return Ptr(members)
        fname, line, col = str(node.dim.coord).split(":")
        line = int(line) -1
        col = int(col) -1

        lines = _global.SAUCE.splitlines()
        lno = lines[line]
        sta_idx = lno.rindex("[")
        end_idx = lno.index("]", sta_idx)
        expr = lno[sta_idx+1:end_idx]
        size = eval_c_expr(expr, "\n".join(f"#include<{h}>" for h in _global.INCLUDES) )

        return List(members, size)
    if isinstance(node, c_ast.Union):
        if node.decls is None: return Opaque(node.name)
        m = {}
        for d in node.decls:
            m[d.name] = parse_type(d.type)
        return Union(m)
    if isinstance(node, c_ast.FuncDecl): return Ptr(Opaque("func"))
    node.show()
    raise Exception("Unimplemented Type Node") 
