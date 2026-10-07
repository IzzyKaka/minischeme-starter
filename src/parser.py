"""语法分析：词列表 -> 表达式（嵌套的数据结构）。

表达式的表示：
  * 数 / 布尔 / 字符串 —— Python 的 int、float、bool、str；
  * 符号             —— Symbol；
  * 列表             —— 一串 Pair，以 NIL 结尾；`()` 就是 NIL；
  * `'x`             —— 展开成列表 (quote x)，求值器再按特殊形式处理。

只负责“形状”，不做任何求值。
"""

from datatypes import NIL, Pair, Symbol, list_to_pairs
from errors import SchemeError
from tokenizer import Token, tokenize

# 字符串里合法的转义（spec §3）
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def parse_program(source: str) -> list:
    """把一段程序文本解析成顶层表达式列表（可跨行、可为空）。"""
    return parse_tokens(tokenize(source))


def parse_tokens(tokens: list[Token]) -> list:
    """把词列表解析成表达式列表。"""
    expressions: list = []
    index = 0
    while index < len(tokens):
        expression, index = _parse_expression(tokens, index)
        expressions.append(expression)
    return expressions


def _parse_expression(tokens: list[Token], index: int) -> tuple[object, int]:
    """解析一个表达式，返回（表达式、下一个词的下标）。"""
    if index >= len(tokens):
        raise SchemeError("表达式没有结束（缺少右括号）")
    token = tokens[index]

    if token.kind == "quote":
        inner, index = _parse_expression(tokens, index + 1)
        if index >= len(tokens):
            raise SchemeError(f"line {token.line}: quote 后面缺少表达式")
        return Pair(Symbol("quote"), Pair(inner, NIL)), index

    if token.kind == "atom":
        return _parse_atom(token.text, token.line), index + 1

    if token.kind == "string":
        return unescape_string(token.text), index + 1

    if token.kind == "open":
        return _parse_list(tokens, index + 1, token.line)

    raise SchemeError(f"line {token.line}: 多余的右括号")


def _parse_list(tokens: list[Token], index: int, line: int) -> tuple[object, int]:
    """解析 `(...)`，收集到右括号为止的所有表达式。"""
    items: list = []
    while True:
        if index >= len(tokens):
            raise SchemeError(f"line {line}: 括号没有闭合")
        token = tokens[index]
        if token.kind == "close":
            return list_to_pairs(items), index + 1
        if token.kind == "quote":
            inner, index = _parse_expression(tokens, index)
            items.append(inner)
            continue
        expression, index = _parse_expression(tokens, index)
        items.append(expression)


def _parse_atom(text: str, line: int):
    """把一个 atom 文本解释成数、布尔或符号。"""
    if text in ("#t", "#f"):
        return text == "#t"
    number = _try_number(text)
    if number is not None:
        return number
    return Symbol(text)


def _try_number(text: str):
    """尝试把文本解析成数（先整数再浮点）；不是数就返回 None。"""
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return None


def unescape_string(raw: str) -> str:
    """把字符串字面量的原始内容解码成真正的字符串（`\\n` -> 换行）。"""
    result: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "\\" and index + 1 < len(raw):
            next_char = raw[index + 1]
            if next_char in _ESCAPES:
                result.append(_ESCAPES[next_char])
                index += 2
                continue
            raise SchemeError(f"字符串里有未知转义: \\{next_char}")
        result.append(char)
        index += 1
    return "".join(result)
