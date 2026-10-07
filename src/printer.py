"""打印：值 -> 文本（spec §8）。

两种输出：
  * write_string  —— 值的“带引号”表示，顶层打印结果用它
                     （字符串带引号，换行打印成 \\n）；
  * display_string—— display 用的表示（字符串不带引号、不转义）。
"""

from datatypes import NIL, Pair, Procedure, Symbol

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def write_string(value) -> str:
    """值的标准文本形式（顶层打印 / write 语义）。"""
    if isinstance(value, bool):
        return "#t" if value else "#f"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _float_to_string(value)
    if isinstance(value, str):
        return '"' + _escape(value) + '"'
    if isinstance(value, Symbol):
        return value.name
    if value is NIL:
        return "()"
    if isinstance(value, Pair):
        return _pair_to_string(value)
    if isinstance(value, Procedure):
        return "#<procedure>"
    return str(value)


def display_string(value) -> str:
    """display 用的文本形式：字符串原样输出，其余同 write_string。"""
    if isinstance(value, str):
        return value
    return write_string(value)


def _escape(text: str) -> str:
    return "".join(_ESCAPES.get(char, char) for char in text)


def _float_to_string(value: float) -> str:
    """浮点数的打印：保持 Python 默认形式（0.5 -> 0.5，3.0 -> 3.0）。"""
    return repr(value)


def _pair_to_string(pair: Pair) -> str:
    """点对链的打印：正规列表 (1 2 3)，非正规 (1 . 2)。"""
    items: list[str] = []
    current = pair
    while isinstance(current, Pair):
        items.append(write_string(current.car))
        current = current.cdr
    if current is NIL:
        return "(" + " ".join(items) + ")"
    return "(" + " ".join(items) + " . " + write_string(current) + ")"


__all__ = ["write_string", "display_string"]
