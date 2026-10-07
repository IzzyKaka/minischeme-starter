"""mini-Scheme 的统一错误类型。

解释器内部所有可预期的错误（未绑定变量、错误的参数个数、
把一个数字当过程调用等）都用 SchemeError 抛出，由入口 main.py
统一捕获并打印到 stderr，避免把 Python 的调用栈暴露给用户。
"""


class SchemeError(Exception):
    """mini-Scheme 运行期错误。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message
