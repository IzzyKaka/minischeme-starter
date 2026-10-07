"""求值器：表达式 -> 值（解释器的心脏，spec §4 / §9）。

核心是两个互相递归的函数：

    evaluate(expr, env)  求值一个表达式
    apply_procedure(proc, args)  调用一个过程

evaluate 遇到函数调用就交给 apply_procedure；apply_procedure 执行函数体
时又回到 evaluate。这个循环支撑起递归与高阶函数。

特殊形式（quote / if / cond / and / or / define / lambda / let / begin）
各自决定“先算什么、后算什么”，定义在下方的 SPECIAL_FORMS 表里。
"""

from datatypes import (
    NIL,
    BuiltinProcedure,
    LambdaProcedure,
    Pair,
    Procedure,
    Symbol,
    is_true,
    iter_pair,
)
from environment import Environment
from errors import SchemeError


# ------------------------------------------------------------ 主入口：求值


def evaluate(expr, env: Environment):
    """求值一个表达式，返回 mini-Scheme 的值。"""
    while True:
        # 1) 符号：去环境里查绑定的值
        if isinstance(expr, Symbol):
            return env.lookup(expr.name)

        # 2) 基本值（数、布尔、字符串、空表）与过程对象：求值就是它自己
        if not isinstance(expr, Pair):
            return expr

        # 3) 括号表达式：先看是不是特殊形式
        operator = expr.car
        if isinstance(operator, Symbol) and operator.name in SPECIAL_FORMS:
            handler = SPECIAL_FORMS[operator.name]
            return handler(expr, env)          # 特殊形式自己决定求值顺序

        # 4) 否则是函数调用：先求值操作符和全部实参，再交给 apply
        procedure = evaluate(operator, env)
        args = [evaluate(arg, env) for arg in iter_pair(expr.cdr)]
        if not isinstance(procedure, Procedure):
            raise SchemeError(f"无法调用: {operator} 不是过程")

        # 用户定义的函数：用“尾调用展开”代替递归，避免深递归耗尽 Python 栈。
        if isinstance(procedure, LambdaProcedure):
            env = _extend_environment(procedure, args)
            body = procedure.body
            if not body:
                return None
            for sub in body[:-1]:
                evaluate(sub, env)
            expr = body[-1]                    # 回到循环顶部，继续求值函数体
            continue
        return apply_procedure(procedure, args)


def apply_procedure(procedure: Procedure, args: list):
    """调用一个过程：内置过程直接执行，闭包则新建一层环境求值函数体。"""
    if isinstance(procedure, BuiltinProcedure):
        return procedure.fn(args)
    if isinstance(procedure, LambdaProcedure):
        env = _extend_environment(procedure, args)
        return evaluate_body(procedure.body, env)
    raise SchemeError(f"无法调用: {procedure} 不是过程")


def evaluate_body(body: list, env: Environment):
    """按 begin 语义依次求值函数体，返回最后一个表达式的值。"""
    if not body:
        return None
    for expr in body[:-1]:
        evaluate(expr, env)
    return evaluate(body[-1], env)


def _extend_environment(procedure: LambdaProcedure, args: list) -> Environment:
    """给闭包调用造一层新环境：实参绑到参数名上，外层指向**定义时**的环境。"""
    if len(args) != len(procedure.params):
        raise SchemeError(
            f"{procedure.name}: 参数个数不对，期望 {len(procedure.params)} 个，"
            f"实际 {len(args)} 个"
        )
    env = Environment(parent=procedure.env)
    for name, value in zip(procedure.params, args):
        env.define(name, value)
    return env


# ------------------------------------------------------------ 特殊形式


def _second(pair: Pair):
    """取列表第二项（(f a b ...) 里的 a）。"""
    if not isinstance(pair.cdr, Pair):
        return None
    return pair.cdr.car


def _rest(pair: Pair) -> list:
    """取列表从第二项开始的其余部分，转成 Python 列表。"""
    if not isinstance(pair.cdr, Pair):
        return []
    return list(iter_pair(pair.cdr))


def _eval_quote(expr: Pair, env: Environment):
    """`(quote 数据)`：原样返回，不求值（spec §4.1）。"""
    parts = _rest(expr)
    if len(parts) != 1:
        raise SchemeError("quote: 需要一个参数")
    return parts[0]


def _eval_if(expr: Pair, env: Environment):
    """`(if 测试 真分支 假分支?)`：只求值被选中的那个分支（spec §4.2）。"""
    parts = _rest(expr)
    if len(parts) not in (2, 3):
        raise SchemeError("if: 需要 2 或 3 个参数（测试、真分支、可选假分支）")
    test, consequent = parts[0], parts[1]
    if is_true(evaluate(test, env)):
        return evaluate(consequent, env)
    if len(parts) == 3:
        return evaluate(parts[2], env)
    return None                                # 无假分支且测试为假 -> 无值


def _eval_cond(expr: Pair, env: Environment):
    """`(cond (测试 表达式...) ... (else 表达式...))`（spec §4.3）。"""
    for clause in _rest(expr):
        if not isinstance(clause, Pair):
            raise SchemeError("cond: 每个子句必须是列表")
        parts = list(iter_pair(clause))
        test = parts[0]
        # else 只在最后兜底；遇到它就无条件选中
        is_else = isinstance(test, Symbol) and test.name == "else"
        if is_else:
            if len(parts) == 1:
                raise SchemeError("cond: else 子句里至少要有一个表达式")
            return evaluate_body(parts[1:], env)
        value = evaluate(test, env)
        if is_true(value):
            if len(parts) == 1:
                return value                   # 子句没有表达式 -> 返回测试值
            return evaluate_body(parts[1:], env)
    return None                                # 全部不匹配 -> 无值


def _eval_and(expr: Pair, env: Environment):
    """`(and e1 e2 ...)`：短路，遇到第一个 #f 立刻返回（spec §4.4）。"""
    value = True
    for sub in _rest(expr):
        value = evaluate(sub, env)
        if not is_true(value):
            return False
    return value


def _eval_or(expr: Pair, env: Environment):
    """`(or e1 e2 ...)`：短路，遇到第一个真值立刻返回它。"""
    value = False
    for sub in _rest(expr):
        value = evaluate(sub, env)
        if is_true(value):
            return value
    return value


def _eval_define(expr: Pair, env: Environment):
    """`(define 名 表达式)` 或 `(define (函数名 参数...) 体...)`（spec §4.5）。

    结果是**被定义的符号名**（顶层会把它打印出来）。
    """
    target = _second(expr)
    rest = list(iter_pair(expr.cdr.cdr)) if isinstance(expr.cdr.cdr, Pair) else []

    if isinstance(target, Pair):
        # 定义函数的简写：(define (f x) 体) == (define f (lambda (x) 体))
        name_symbol = target.car
        if not isinstance(name_symbol, Symbol):
            raise SchemeError("define: 函数名必须是符号")
        params = _param_names(target.cdr)
        value = LambdaProcedure(params, rest, env, name=name_symbol.name)
    else:
        name_symbol = target
        if not isinstance(name_symbol, Symbol):
            raise SchemeError("define: 被定义的名字必须是符号")
        if len(rest) != 1:
            raise SchemeError("define: 需要一个值表达式")
        value = evaluate(rest[0], env)         # 先求值右侧，再绑定

    env.define(name_symbol.name, value)
    return name_symbol                         # define 的结果是被定义的名字


def _param_names(params) -> list[str]:
    """把 lambda / define 的参数表转成名字列表（固定参数，不支持可变参数）。"""
    if params is NIL:
        return []
    if not isinstance(params, Pair):
        raise SchemeError("参数表必须是符号列表")
    names = []
    for item in iter_pair(params):
        if not isinstance(item, Symbol):
            raise SchemeError("参数名必须是符号")
        names.append(item.name)
    return names


def _eval_lambda(expr: Pair, env: Environment):
    """`(lambda (参数...) 体...)`：造一个闭包，记住定义处的环境（spec §4.6）。"""
    parts = _rest(expr)
    if len(parts) < 1:
        raise SchemeError("lambda: 缺少参数表")
    params = _param_names(parts[0])
    return LambdaProcedure(params, parts[1:], env)


def _eval_let(expr: Pair, env: Environment):
    """`(let ((名 表达式)...) 体...)`：绑定**并行**求值（spec §4.7）。"""
    parts = _rest(expr)
    if len(parts) < 1:
        raise SchemeError("let: 缺少绑定列表")
    bindings = parts[0]
    if not (bindings is NIL or isinstance(bindings, Pair)):
        raise SchemeError("let: 绑定列表必须是列表")

    names: list[str] = []
    values: list = []
    if isinstance(bindings, Pair):
        for binding in iter_pair(bindings):
            if not isinstance(binding, Pair) or not isinstance(binding.cdr, Pair):
                raise SchemeError("let: 每个绑定必须是 (名 表达式)")
            name = binding.car
            if not isinstance(name, Symbol):
                raise SchemeError("let: 被绑定的名字必须是符号")
            names.append(name.name)
            values.append(evaluate(binding.cdr.car, env))   # 在外层环境求值

    inner = Environment(parent=env)
    for name, value in zip(names, values):
        inner.define(name, value)
    return evaluate_body(parts[1:], inner)


def _eval_begin(expr: Pair, env: Environment):
    """`(begin e1 e2 ...)`：依次求值，返回最后一个的值（spec §4.8）。"""
    return evaluate_body(_rest(expr), env)


SPECIAL_FORMS = {
    "quote": _eval_quote,
    "if": _eval_if,
    "cond": _eval_cond,
    "and": _eval_and,
    "or": _eval_or,
    "define": _eval_define,
    "lambda": _eval_lambda,
    "let": _eval_let,
    "begin": _eval_begin,
}
