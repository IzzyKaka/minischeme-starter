"""环境：变量绑定表 + 指向外层环境的指针。

环境就是一张“名字 -> 值”的表，外加一个指向外层环境的 parent 指针。
查找名字时先查自己，查不到就沿着 parent 往外走——这条链就是词法作用域
（spec §9），也是闭包能“记住定义处环境”的原因（spec §4.6）。
"""

from errors import SchemeError


class Environment:
    """一层环境。全局环境的 parent 为 None。"""

    __slots__ = ("bindings", "parent")

    def __init__(self, parent: "Environment | None" = None) -> None:
        self.bindings: dict[str, object] = {}
        self.parent = parent

    def define(self, name: str, value: object) -> None:
        """在当前层绑定（或覆盖）一个名字。define 用这个方法。"""
        self.bindings[name] = value

    def lookup(self, name: str):
        """查找名字的值：先本层，再逐层向外；找不到就报错。"""
        env: "Environment | None" = self
        while env is not None:
            if name in env.bindings:
                return env.bindings[name]
            env = env.parent
        raise SchemeError(f"未绑定的变量: {name}")

    def set(self, name: str, value: object) -> None:
        """给已存在的绑定赋新值（沿着外层链找）。找不到就报错。"""
        env: "Environment | None" = self
        while env is not None:
            if name in env.bindings:
                env.bindings[name] = value
                return
            env = env.parent
        raise SchemeError(f"无法赋值：未绑定的变量: {name}")

    def __repr__(self) -> str:
        names = ", ".join(sorted(self.bindings))
        return f"Environment({names})"
