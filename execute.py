import subprocess
from sys import stdout

def exec_c(sauce : str):
    e  = subprocess.Popen(("echo", sauce), stdout=subprocess.PIPE)
    e.wait()
    cl = subprocess.Popen(("clang", "-S", "-emit-llvm", "-xc", "-", "-o-"), stdin=e.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ll = subprocess.Popen(("lli"), stdin=cl.stdout, stdout=subprocess.PIPE)
    ll.wait()
    try:
        return int(ll.stdout.read())
    except:
        print(sauce)
        print("Failed")
        print(cl.stderr.read().decode("utf8"))
        exit(1)


def eval_c_expr(e : str, ctx : str):
    """
    Returns the value of a c expression, assuming it returns an integer
    """
    source =  ctx+f"\n#include<stdio.h>\n\nint main(){{  printf(\"%lu\", {e}); return 0; }}"

    return exec_c(source)
