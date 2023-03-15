# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from ast import (
    literal_eval,
)

from pyparsing import (
    Keyword,
    Literal,
    QuotedString,
    Suppress,
    Word,
    alphas,
    delimitedList,
    hexnums,
    infixNotation,
    nums,
    opAssoc,
)

from ..constants import (
    IDF_VERSION_MAJOR,
    IDF_VERSION_MINOR,
    IDF_VERSION_PATCH,
)
from .soc_header import (
    SOC_HEADERS,
)


class Stmt:
    """
    Statement
    """

    def get_value(self, target):  # type: (str) -> any
        """
        Lazy calculated. All subclasses of `Stmt` should implement this function.

        :param target: ESP-IDF target
        :type target: str
        :return: the value of the statement
        """
        raise NotImplementedError('Please implement this function in sub classes')


class ChipAttr(Stmt):
    """
    Attributes defined in SOC Header Files and some other keywords

    Supported keywords:
    - IDF_TARGET: target
    - INCLUDE_DEFAULT: take the default build targets into account or not
    - IDF_VERSION_MAJOR: major version of ESP-IDF
    - IDF_VERSION_MINOR: minor version of ESP-IDF
    - IDF_VERSION_PATCH: patch version of ESP-IDF
    """

    def __init__(self, t):
        self.attr = t[0]

    def get_value(self, target):  # type: (str) -> any
        from .manifest import FolderRule  # lazy-load

        if self.attr == 'IDF_TARGET':
            return target

        if self.attr == 'INCLUDE_DEFAULT':
            return 1 if target in FolderRule.DEFAULT_BUILD_TARGETS else 0

        if self.attr == 'IDF_VERSION_MAJOR':
            return IDF_VERSION_MAJOR

        if self.attr == 'IDF_VERSION_MINOR':
            return IDF_VERSION_MINOR

        if self.attr == 'IDF_VERSION_PATCH':
            return IDF_VERSION_PATCH

        if self.attr in SOC_HEADERS[target]:
            return SOC_HEADERS[target][self.attr]

        return 0  # default return 0 as false


class Integer(Stmt):
    def __init__(self, t):
        self.expr = t[0]

    def get_value(self, target):  # type: (str) -> any
        return literal_eval(self.expr)


class String(Stmt):
    def __init__(self, t):
        self.expr = t[0]

    def get_value(self, target):  # type: (str) -> any
        return literal_eval('"{}"'.format(self.expr))  # double quotes is swallowed by QuotedString


class List_(Stmt):
    def __init__(self, t):
        self.expr = t

    def get_value(self, target):  # type: (str) -> any
        return [item.get_value(target) for item in self.expr]


class BoolStmt(Stmt):
    def __init__(self, t):
        self.left = t[0]  # type: Stmt
        self.comparison = t[1]  # type: str
        self.right = t[2]  # type: Stmt

    def get_value(self, target):  # type: (str) -> any
        if self.comparison == '==':
            return self.left.get_value(target) == self.right.get_value(target)

        if self.comparison == '!=':
            return self.left.get_value(target) != self.right.get_value(target)

        if self.comparison == '>':
            return self.left.get_value(target) > self.right.get_value(target)

        if self.comparison == '>=':
            return self.left.get_value(target) >= self.right.get_value(target)

        if self.comparison == '<':
            return self.left.get_value(target) < self.right.get_value(target)

        if self.comparison == '<=':
            return self.left.get_value(target) <= self.right.get_value(target)

        if self.comparison == 'not in':
            return self.left.get_value(target) not in self.right.get_value(target)

        if self.comparison == 'in':
            return self.left.get_value(target) in self.right.get_value(target)

        raise ValueError('Unsupported comparison operator: "{}"'.format(self.comparison))


class BoolExpr(Stmt):
    pass


class BoolAnd(BoolExpr):
    def __init__(self, t):
        self.left = t[0][0]  # type: BoolStmt
        self.right = t[0][2]  # type: BoolStmt

    def get_value(self, target):  # type: (str) -> any
        return self.left.get_value(target) and self.right.get_value(target)


class BoolOr(BoolExpr):
    def __init__(self, t):
        self.left = t[0][0]  # type: BoolStmt
        self.right = t[0][2]  # type: BoolStmt

    def get_value(self, target):  # type: (str) -> any
        return self.left.get_value(target) or self.right.get_value(target)


CAP_WORD = Word(alphas.upper(), nums + alphas.upper() + '_').setParseAction(ChipAttr)

DECIMAL_NUMBER = Word(nums)
HEX_NUMBER = Literal('0x') + Word(hexnums)
INTEGER = (HEX_NUMBER | DECIMAL_NUMBER).setParseAction(Integer)

STRING = QuotedString('"').setParseAction(String)

LIST = Suppress('[') + delimitedList(INTEGER | STRING).setParseAction(List_) + Suppress(']')

BOOL_OPERAND = CAP_WORD | INTEGER | STRING | LIST

EQ = Keyword('==').setParseAction(lambda t: t[0])
NE = Keyword('!=').setParseAction(lambda t: t[0])
LE = Keyword('<=').setParseAction(lambda t: t[0])
LT = Keyword('<').setParseAction(lambda t: t[0])
GE = Keyword('>=').setParseAction(lambda t: t[0])
GT = Keyword('>').setParseAction(lambda t: t[0])
NOT_IN = Keyword('not in').setParseAction(lambda t: t[0])
IN = Keyword('in').setParseAction(lambda t: t[0])

BOOL_STMT = BOOL_OPERAND + (EQ | NE | LE | LT | GE | GT | NOT_IN | IN) + BOOL_OPERAND
BOOL_STMT.setParseAction(BoolStmt)

AND = Keyword('and')
OR = Keyword('or')

BOOL_EXPR = infixNotation(
    BOOL_STMT,
    [
        (AND, 2, opAssoc.LEFT, BoolAnd),
        (OR, 2, opAssoc.LEFT, BoolOr),
    ],
)
