import subprocess
from sys import stdout

def exec_c(sauce : str):
    e  = subprocess.Popen(("echo", sauce), stdout=subprocess.PIPE)
    e.wait()
    cl = subprocess.Popen(("clang", "-S", "-emit-llvm", "-xc", "-", "-o-"), stdin=e.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    ll = subprocess.Popen(("lli"), stdin=cl.stdout, stdout=subprocess.PIPE)
    ll.wait()
    return int(ll.stdout.read())


def eval_c_expr(e : str, ctx : str):
    """
    Returns the value of a c expression, assuming it returns an integer
    """
    source = ctx + f"\n\n\nint main(){{  printf(\"%lu\", {e}); return 0; }}"

    return exec_c(source)
