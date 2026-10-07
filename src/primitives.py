"""内置过程库：spec §5 的全部标准函数，装进初始全局环境。

内置过程与特殊形式的区别：调用内置过程时，操作符和所有实参**先求值**，
然后一次性交给这里的 Python 函数；返回值是 mini-Scheme 的值
（None 表示“无值”，顶层不打印，display/newline 就是这样）。

每个内置过程都写成 (名字, Python 函数) 的形式登记在 BUILTINS 里，
新增一个内置函数只需要往表里加一行。
"""

import math
import sys

from datatypes import (
    NIL,
    BuiltinProcedure,
    Pair,
    Procedure,
    Symbol,
    is_number,
    is_proper_list,
    iter_pair,
    length_of,
    list_to_pairs,
)
from environment import Environment
from errors import SchemeError
from printer import display_string


# ------------------------------------------------------------ 参数检查工具


def _expect_numbers(name: str, args: list) -> None:
    for arg in args:
        if not is_number(arg):
            raise SchemeError(f"{name}: 参数必须是数，收到 {arg!r}")


def _trunc_div(a: int, b: int) -> int:
    """整数除法，商向零截断（Python 的 // 是向下取整，不能用）。

    (/ -7 2) 与 (quotient -7 2) 都要求得到 -3，而不是 -4。
    """
    if b == 0:
        raise SchemeError("除数不能为 0")
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


# ------------------------------------------------------------------ 算术


def _add(args):
    _expect_numbers("+", args)
    total = 0
    for arg in args:
        total += arg
    return total


def _multiply(args):
    _expect_numbers("*", args)
    total = 1
    for arg in args:
        total *= arg
    return total


def _subtract(args):
    _expect_numbers("-", args)
    if not args:
        raise SchemeError("-: 至少需要一个参数")
    if len(args) == 1:
        return -args[0]
    result = args[0]
    for arg in args[1:]:
        result -= arg
    return result


def _divide(args):
    """`/`：整数相除得整数商（向零截断），出现浮点数才走浮点除法。"""
    _expect_numbers("/", args)
    if not args:
        raise SchemeError("/: 至少需要一个参数")
    if len(args) == 1:                        # 单参数求倒数，结果是浮点
        if args[0] == 0:
            raise SchemeError("/: 除数不能为 0")
        return 1 / args[0]
    all_integers = all(isinstance(arg, int) for arg in args)
    result = args[0]
    for arg in args[1:]:
        if arg == 0:
            raise SchemeError("/: 除数不能为 0")
        result = _trunc_div(result, arg) if all_integers else result / arg
    return result


def _modulo(args):
    _expect_numbers("modulo", args)
    if len(args) != 2:
        raise SchemeError("modulo: 需要两个参数")
    a, b = args
    if b == 0:
        raise SchemeError("modulo: 除数不能为 0")
    if isinstance(a, int) and isinstance(b, int):
        return a % b                          # 结果的符号跟除数（R5RS modulo）
    return math.fmod(a, b)


def _quotient(args):
    _expect_numbers("quotient", args)
    if len(args) != 2:
        raise SchemeError("quotient: 需要两个参数")
    a, b = args
    if not isinstance(a, int) or not isinstance(b, int):
        raise SchemeError("quotient: 参数必须是整数")
    return _trunc_div(a, b)


def _expt(args):
    _expect_numbers("expt", args)
    if len(args) != 2:
        raise SchemeError("expt: 需要两个参数")
    return args[0] ** args[1]


def _abs(args):
    _expect_numbers("abs", args)
    if len(args) != 1:
        raise SchemeError("abs: 需要一个参数")
    return abs(args[0])


# ------------------------------------------------------------------ 比较


def _chain(compare):
    """把二元比较包装成链式比较（相邻两两都成立才为真）。"""

    def builtin(args):
        if len(args) < 2:
            raise SchemeError("比较运算: 至少需要两个参数")
        for left, right in zip(args, args[1:]):
            if not compare(left, right):
                return False
        return True

    return builtin


def _order_key(name: str, value):
    """把值映射成可比较的键：数之间比数值，符号/字符串之间比内容。"""
    if is_number(value):
        return (0, value)
    if isinstance(value, Symbol):
        return (1, value.name)
    if isinstance(value, str):
        return (1, value)
    raise SchemeError(f"{name}: 参数必须是数或符号/字符串")


def _less_than(left, right):
    return _order_key("<", left) < _order_key("<", right)


def _greater_than(left, right):
    return _order_key(">", left) > _order_key(">", right)


def _less_equal(left, right):
    return _order_key("<=", left) <= _order_key("<=", right)


def _greater_equal(left, right):
    return _order_key(">=", left) >= _order_key(">=", right)


def _numeric_equal(left, right):
    """`=`：数按数值比较，符号/字符串按内容比较（spec §5）。"""
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left is right
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    return False


# ------------------------------------------------------------------ 布尔


def _not(args):
    if len(args) != 1:
        raise SchemeError("not: 需要一个参数")
    return args[0] is False                   # 只有 #f 是假


# ------------------------------------------------------------------ 列表


def _cons(args):
    if len(args) != 2:
        raise SchemeError("cons: 需要两个参数")
    return Pair(args[0], args[1])


def _car(args):
    if len(args) != 1:
        raise SchemeError("car: 需要一个参数")
    if not isinstance(args[0], Pair):
        raise SchemeError("car: 参数必须是点对")
    return args[0].car


def _cdr(args):
    if len(args) != 1:
        raise SchemeError("cdr: 需要一个参数")
    if not isinstance(args[0], Pair):
        raise SchemeError("cdr: 参数必须是点对")
    return args[0].cdr


def _list(args):
    return list_to_pairs(args)


def _length(args):
    if len(args) != 1:
        raise SchemeError("length: 需要一个参数")
    value = args[0]
    if value is NIL:
        return 0
    if not isinstance(value, Pair):
        raise SchemeError("length: 参数必须是列表")
    return length_of(value)


def _append(args):
    """拼接若干列表；最后一个参数可以是任意值（可以产生非正规列表）。"""
    if not args:
        return NIL
    if len(args) == 1:
        return args[0]
    items = []
    for lst in args[:-1]:
        if lst is NIL:
            continue
        if not isinstance(lst, Pair):
            raise SchemeError("append: 除最后一个外，参数都必须是列表")
        items.extend(iter_pair(lst))
    return list_to_pairs(items, tail=args[-1])


def _is_null(args):
    if len(args) != 1:
        raise SchemeError("null?: 需要一个参数")
    return args[0] is NIL


def _is_pair(args):
    if len(args) != 1:
        raise SchemeError("pair?: 需要一个参数")
    return isinstance(args[0], Pair)


def _is_list(args):
    if len(args) != 1:
        raise SchemeError("list?: 需要一个参数")
    return is_proper_list(args[0])


# ------------------------------------------------------------------ 谓词


def _is_number(args):
    if len(args) != 1:
        raise SchemeError("number?: 需要一个参数")
    return is_number(args[0])


def _is_boolean(args):
    if len(args) != 1:
        raise SchemeError("boolean?: 需要一个参数")
    return isinstance(args[0], bool)


def _is_symbol(args):
    if len(args) != 1:
        raise SchemeError("symbol?: 需要一个参数")
    return isinstance(args[0], Symbol)


def _is_string(args):
    if len(args) != 1:
        raise SchemeError("string?: 需要一个参数")
    return isinstance(args[0], str)


def _is_procedure(args):
    if len(args) != 1:
        raise SchemeError("procedure?: 需要一个参数")
    return isinstance(args[0], Procedure)


def _numeric_predicate(name, test):
    """生成 zero? / even? / odd? 这类数值谓词。"""

    def builtin(args):
        if len(args) != 1:
            raise SchemeError(f"{name}: 需要一个参数")
        value = args[0]
        if not is_number(value):
            raise SchemeError(f"{name}: 参数必须是数")
        return test(value)

    return builtin


def _eq(args):
    """`eq?`：数/布尔/符号按值比较，其余（列表、字符串等）比同一性。"""
    if len(args) != 2:
        raise SchemeError("eq?: 需要两个参数")
    left, right = args
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, Symbol) or isinstance(right, Symbol):
        return left is right
    if is_number(left) and is_number(right):
        return left == right
    return left is right


def _equal(args):
    """`equal?`：结构相等（逐层比较），且区分类型。"""
    if len(args) != 2:
        raise SchemeError("equal?: 需要两个参数")
    return _equal_impl(args[0], args[1])


def _equal_impl(left, right) -> bool:
    # 布尔要单独判断：Python 里 True == 1，不先判类型会把 #t 和 1 判成相等。
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if is_number(left) or is_number(right):
        return is_number(left) and is_number(right) and left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, Symbol) or isinstance(right, Symbol):
        return isinstance(left, Symbol) and isinstance(right, Symbol) and left is right
    if left is NIL or right is NIL:
        return left is right
    if isinstance(left, Pair) and isinstance(right, Pair):
        return _equal_impl(left.car, right.car) and _equal_impl(left.cdr, right.cdr)
    return left is right


# ------------------------------------------------------------------ 输出


def _display(args):
    """打印一个值（字符串不带引号），不换行；返回“无值”（顶层不打印）。"""
    if len(args) != 1:
        raise SchemeError("display: 需要一个参数")
    sys.stdout.write(display_string(args[0]))
    return None


def _newline(args):
    """输出一个换行；返回“无值”。"""
    sys.stdout.write("\n")
    return None


# ------------------------------------------------------------ 内置过程表

BUILTINS = {
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "modulo": _modulo,
    "quotient": _quotient,
    "expt": _expt,
    "abs": _abs,
    "=": _chain(_numeric_equal),
    "<": _chain(_less_than),
    ">": _chain(_greater_than),
    "<=": _chain(_less_equal),
    ">=": _chain(_greater_equal),
    "not": _not,
    "cons": _cons,
    "car": _car,
    "cdr": _cdr,
    "list": _list,
    "length": _length,
    "append": _append,
    "null?": _is_null,
    "pair?": _is_pair,
    "list?": _is_list,
    "number?": _is_number,
    "boolean?": _is_boolean,
    "symbol?": _is_symbol,
    "string?": _is_string,
    "procedure?": _is_procedure,
    "zero?": _numeric_predicate("zero?", lambda x: x == 0),
    "even?": _numeric_predicate("even?", lambda x: int(x) % 2 == 0),
    "odd?": _numeric_predicate("odd?", lambda x: int(x) % 2 != 0),
    "eq?": _eq,
    "equal?": _equal,
    "display": _display,
    "newline": _newline,
}


def make_global_environment() -> Environment:
    """造一个只装着内置过程的全局环境（spec §2：初始环境为空）。"""
    env = Environment(parent=None)
    for name, function in BUILTINS.items():
        env.define(name, BuiltinProcedure(function, name))
    return env
