"""mini-Scheme 的值表示（数据类型层）。

流水线里其它模块都只依赖这里定义的结构：

    符号 Symbol      —— 名字；做了驻留（intern），同名符号是同一个对象，
                        这样 eq? 对符号可以直接用身份比较。
    点对 Pair        —— 有两个字段 car / cdr，列表就是一串点对（spec §6）。
    空表 NIL         —— 单例，表示 ()。
    过程 Procedure   —— 内置过程 BuiltinProcedure / 用户闭包 LambdaProcedure。

基本值直接用 Python 原生类型表示：int / float 是数，bool 是布尔，
str 是字符串。注意 Python 里 bool 是 int 的子类，凡是要判断“是不是数”
的地方都必须先把 bool 排除掉（否则 (#t) 会被当成数字）。
"""


class Symbol:
    """符号：表示一个名字。同名符号全局唯一（驻留）。"""

    __slots__ = ("name",)
    _table: dict[str, "Symbol"] = {}

    def __new__(cls, name: str) -> "Symbol":
        symbol = cls._table.get(name)
        if symbol is None:
            symbol = object.__new__(cls)
            symbol.name = name
            cls._table[name] = symbol
        return symbol

    def __repr__(self) -> str:
        return f"Symbol({self.name!r})"


class Pair:
    """点对：列表的基本单元。(1 2 3) 就是 Pair(1, Pair(2, Pair(3, NIL)))。"""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr) -> None:
        self.car = car
        self.cdr = cdr

    def __repr__(self) -> str:
        return f"Pair({self.car!r}, {self.cdr!r})"


class Nil:
    """空表 ()，全局只有一个实例（NIL）。"""

    __slots__ = ()
    _instance = None

    def __new__(cls) -> "Nil":
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "()"


NIL = Nil()


class Procedure:
    """所有可调用对象的共同基类，供 procedure? 判断使用。"""

    __slots__ = ("name",)

    def __init__(self, name: str = "anonymous") -> None:
        self.name = name


class BuiltinProcedure(Procedure):
    """内置过程：包裹一个 Python 函数，调用时收到已求值的实参列表。"""

    __slots__ = ("fn",)

    def __init__(self, fn, name: str) -> None:
        super().__init__(name)
        self.fn = fn

    def __repr__(self) -> str:
        return f"#<procedure {self.name} (builtin)>"


class LambdaProcedure(Procedure):
    """用户定义的闭包：参数表、函数体、以及定义时捕获的环境（词法作用域）。"""

    __slots__ = ("params", "body", "env")

    def __init__(self, params, body, env, name: str = "lambda") -> None:
        super().__init__(name)
        self.params = params          # 参数名列表（list[str]）
        self.body = body              # 函数体表达式列表（list）
        self.env = env                # 定义处的环境（闭包的关键）

    def __repr__(self) -> str:
        return f"#<procedure {self.name}>"


# ---------------------------------------------------------------- 列表工具


def iter_pair(pair):
    """按 cdr 链依次产出一个（正规）列表里的元素；遇到非点对结尾就报错。

    quote 出来的数据、cons 链都用它来遍历。
    """
    current = pair
    while isinstance(current, Pair):
        yield current.car
        current = current.cdr
    if current is not NIL:
        raise TypeError("improper list")


def list_to_pairs(items, tail=NIL):
    """把 Python 列表转成 mini-Scheme 的点对链，末尾接 tail。

    list_to_pairs([1, 2, 3])        -> (1 2 3)
    list_to_pairs([1], tail=2)      -> (1 . 2)
    """
    result = tail
    for item in reversed(list(items)):
        result = Pair(item, result)
    return result


def pairs_to_list(pair):
    """把一个点对链转成 Python 列表（用于参数表、let 绑定表等语法结构）。"""
    return list(iter_pair(pair))


def length_of(pair) -> int:
    """列表长度，非正规列表报错。"""
    count = 0
    for _ in iter_pair(pair):
        count += 1
    return count


def is_proper_list(value) -> bool:
    """是否是正规列表（以 NIL 结尾的点对链）；NIL 本身也算列表。"""
    if value is NIL:
        return True
    current = value
    while isinstance(current, Pair):
        current = current.cdr
    return current is NIL


def is_number(value) -> bool:
    """是否是数。Python 的 bool 是 int 子类，必须先排除。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_true(value) -> bool:
    """mini-Scheme 的真假判定：只有 #f 是假，0 / () / "" 都是真（spec §9）。"""
    return value is not False
