# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import operator
import os
from ast import (
    literal_eval,
)
from typing import (
    Any,
)

from packaging.version import (
    Version,
)
from pyparsing import (
    Keyword,
    Literal,
    MatchFirst,
    ParseResults,
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
    IDF_VERSION,
    IDF_VERSION_MAJOR,
    IDF_VERSION_MINOR,
    IDF_VERSION_PATCH,
)
from ..utils import (
    InvalidIfClause,
    InvalidInput,
    to_version,
)
from .soc_header import (
    SOC_HEADERS,
)


class Stmt:
    """
    Statement
    """

    def get_value(self, target: str, config_name: str) -> Any:
        """
        Lazy calculated. All subclasses of `Stmt` should implement this function.

        :param target: ESP-IDF target
        :type target: str
        :param config_name: config name
        :type target: str
        :return: the value of the statement
        """
        raise NotImplementedError('Please implement this function in sub classes')


class ChipAttr(Stmt):
    """
    Attributes defined in SOC Header Files and other keywords as followed:

    - IDF_TARGET: target
    - INCLUDE_DEFAULT: take the default build targets into account or not
    - IDF_VERSION_MAJOR: major version of ESP-IDF
    - IDF_VERSION_MINOR: minor version of ESP-IDF
    - IDF_VERSION_PATCH: patch version of ESP-IDF
    - CONFIG_NAME: config name defined in the config rules
    """

    def __init__(self, t: ParseResults):
        self.attr: str = t[0]

    def get_value(self, target: str, config_name: str) -> Any:
        from .manifest import FolderRule  # lazy-load

        if self.attr == 'IDF_TARGET':
            return target

        if self.attr == 'INCLUDE_DEFAULT':
            return 1 if target in FolderRule.DEFAULT_BUILD_TARGETS else 0

        if self.attr == 'IDF_VERSION':
            return IDF_VERSION

        if self.attr == 'IDF_VERSION_MAJOR':
            return IDF_VERSION_MAJOR

        if self.attr == 'IDF_VERSION_MINOR':
            return IDF_VERSION_MINOR

        if self.attr == 'IDF_VERSION_PATCH':
            return IDF_VERSION_PATCH

        if self.attr == 'CONFIG_NAME':
            return config_name

        if self.attr in SOC_HEADERS[target]:
            return SOC_HEADERS[target][self.attr]

        # for non-keyword cap words, check if it is defined in the environment variables
        if self.attr in os.environ:
            return os.environ[self.attr]

        return 0  # default return 0 as false


class Integer(Stmt):
    def __init__(self, t: ParseResults):
        self.expr: str = t[0]

    def get_value(self, target: str, config_name: str) -> Any:  # noqa: ARG002
        return literal_eval(self.expr)


class String(Stmt):
    def __init__(self, t: ParseResults):
        self.expr: str = t[0]

    def get_value(self, target: str, config_name: str) -> Any:  # noqa: ARG002
        return literal_eval(f'"{self.expr}"')  # double quotes is swallowed by QuotedString


class List_(Stmt):
    def __init__(self, t: ParseResults):
        self.expr = t

    def get_value(self, target: str, config_name: str) -> Any:
        return [item.get_value(target, config_name) for item in self.expr]


class BoolStmt(Stmt):
    _OP_DICT = {
        '==': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '>=': operator.ge,
        '<': operator.lt,
        '<=': operator.le,
        'not in': lambda x, y: x not in y,
        'in': lambda x, y: x in y,
    }

    def __init__(self, t: ParseResults):
        self.left: Stmt = t[0]
        self.comparison: str = t[1]
        self.right: Stmt = t[2]

    def get_value(self, target: str, config_name: str) -> Any:
        _l = self.left.get_value(target, config_name)
        _r = self.right.get_value(target, config_name)

        if self.comparison not in ['in', 'not in']:
            # will use version comparison if any of the operands is a Version
            if any(isinstance(x, Version) for x in [_l, _r]):
                _l = to_version(_l)
                _r = to_version(_r)
        else:
            # use str for "in" and "not in" operator
            if isinstance(_l, Version):
                _l = str(_l)
            if isinstance(_r, Version):
                _r = str(_r)

        if self.comparison in self._OP_DICT:
            return self._OP_DICT[self.comparison](_l, _r)

        raise InvalidInput(f'Unsupported comparison operator: "{self.comparison}"')


class BoolExpr(Stmt):
    pass


def _and(_l, _r):
    return _l and _r


def _or(_l, _r):
    return _l or _r


class BoolOrAnd(BoolExpr):
    def __init__(self, t: ParseResults):
        if len(t[0]) > 3:
            raise InvalidIfClause(
                'Chaining "and"/"or" is not allowed. Please use paratheses instead. '
                'For example: "a and b and c" should be "(a and b) and c".'
            )
        self.left: BoolStmt = t[0][0]
        self.right: BoolStmt = t[0][2]

        if t[0][1] == 'and':
            self.operation = _and
        if t[0][1] == 'or':
            self.operation = _or

    def get_value(self, target: str, config_name: str) -> Any:
        return self.operation(self.left.get_value(target, config_name), self.right.get_value(target, config_name))


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
        (MatchFirst((AND, OR)), 2, opAssoc.LEFT, BoolOrAnd),
    ],
)
