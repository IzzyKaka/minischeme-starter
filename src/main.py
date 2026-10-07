#!/usr/bin/env python3
"""mini-Scheme 解释器入口（评分器按 src/main.py 这个路径调用）。

用法（spec §2）：
    python3 src/main.py file1.scm [file2.scm ...]   # 依次求值每个文件
    python3 src/main.py < program.scm               # 无参数时从标准输入读

每个顶层表达式的结果独占一行打印；结果为“无值”（如 display、newline）
时不打印。多个文件共享同一个全局环境。

为了保证深层递归（fib / sum-to）不会撑爆 Python 的调用栈，
真正的执行被放进一个栈空间更大的线程里。
"""

import os
import sys
import threading

# 以脚本方式运行时，把 src/ 目录放进模块搜索路径，保证同目录模块可导入。
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from environment import Environment          # noqa: E402
from errors import SchemeError               # noqa: E402
from evaluator import evaluate               # noqa: E402
from parser import parse_program             # noqa: E402
from primitives import make_global_environment  # noqa: E402
from printer import write_string             # noqa: E402

RECURSION_LIMIT = 100_000
STACK_SIZE = 64 * 1024 * 1024                # 64 MB


def run_source(source: str, env: Environment, out=sys.stdout) -> None:
    """求值一段程序文本，把每个顶层结果打印成一行。"""
    for expr in parse_program(source):
        value = evaluate(expr, env)
        if value is not None:                # 无值不打印（display / newline）
            out.write(write_string(value) + "\n")
    out.flush()


def read_source(path: str) -> str:
    """读取一个源文件；读不到就给出清晰的错误。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise SchemeError(f"无法读取文件 {path}: {error}") from error


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    env = make_global_environment()
    try:
        if argv:
            for path in argv:                # 多个文件共享同一个全局环境
                run_source(read_source(path), env)
        else:
            run_source(sys.stdin.read(), env)
    except SchemeError as error:
        sys.stdout.flush()
        print(f"错误: {error}", file=sys.stderr)
        return 1
    except RecursionError:
        sys.stdout.flush()
        print("错误: 递归层数过深", file=sys.stderr)
        return 1
    return 0


def _run_with_big_stack() -> int:
    """在大栈线程里跑解释器（深递归友好），返回退出码。"""
    result = {"code": 1}

    def target():
        result["code"] = main()

    sys.setrecursionlimit(RECURSION_LIMIT)
    try:
        threading.stack_size(STACK_SIZE)
    except (ValueError, RuntimeError):
        pass                                  # 某些平台不支持，退回默认栈
    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    return result["code"]


if __name__ == "__main__":
    sys.exit(_run_with_big_stack())
