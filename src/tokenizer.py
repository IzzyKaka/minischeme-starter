"""词法分析：程序文本 -> 词（token）列表。

只做“切词”这一件事，不理解结构：

  * `;` 到行尾是注释，直接丢弃；
  * `(` `)` 各是一个词；
  * `'` 是一个词（quote 的简写，由语法层展开成 (quote ...)）；
  * 双引号包住的部分是一个 string 词（空格不分隔，保留原始文本）；
  * 其余连续字符是一个 atom 词（数字、#t/#f、符号都在这里，
    由语法层负责解释成具体的值）。

每个词记录所在行号，报错时能指出位置。
"""

from dataclasses import dataclass

# 能终止一个 atom 的字符：空白、括号、引号、注释起始。
_DELIMITERS = set(" \t\r\n\f\v()'\";")


@dataclass(frozen=True)
class Token:
    """一个词。kind 取 'open' | 'close' | 'quote' | 'string' | 'atom'。"""

    kind: str
    text: str
    line: int


def tokenize(source: str) -> list[Token]:
    """把整段程序文本切成词列表。"""
    tokens: list[Token] = []
    index = 0
    line = 1
    length = len(source)

    while index < length:
        char = source[index]

        # 换行要单独处理：既分隔词，也要更新行号。
        if char == "\n":
            line += 1
            index += 1
            continue

        if char in " \t\r\f\v":
            index += 1
            continue

        if char == ";":                      # 注释：丢弃到行尾
            while index < length and source[index] != "\n":
                index += 1
            continue

        if char == "(":
            tokens.append(Token("open", "(", line))
            index += 1
            continue

        if char == ")":
            tokens.append(Token("close", ")", line))
            index += 1
            continue

        if char == "'":
            tokens.append(Token("quote", "'", line))
            index += 1
            continue

        if char == '"':
            text, index, line = _read_string(source, index, line)
            tokens.append(Token("string", text, line))
            continue

        start = index
        while index < length and source[index] not in _DELIMITERS:
            index += 1
        if index == start:                   # 理论上到不了这里，留作兜底
            raise ValueError(f"line {line}: 无法识别的字符 {char!r}")
        tokens.append(Token("atom", source[start:index], line))

    return tokens


def _read_string(source: str, index: int, line: int) -> tuple[str, int, int]:
    """读取一个字符串字面量。

    index 指向开头的双引号；返回（原始内容（不含两侧引号）、
    结束后的下标、结束处的行号）。转义字符在这里只做“跳过”，
    `\\n` 之类的真正解码交给语法层 unescape_string。
    """
    index += 1                               # 吃掉开头的引号
    chunks: list[str] = []
    while True:
        if index >= len(source):
            raise ValueError(f"line {line}: 字符串没有闭合的双引号")
        char = source[index]
        if char == '"':
            return "".join(chunks), index + 1, line
        if char == "\\":                     # 转义：连同下一个字符一起收下
            if index + 1 >= len(source):
                raise ValueError(f"line {line}: 字符串结尾的反斜杠没有内容")
            chunks.append(source[index:index + 2])
            index += 2
            continue
        if char == "\n":
            line += 1
        chunks.append(char)
        index += 1
