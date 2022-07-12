# SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import Path

from pyparsing import (
    ParseException,
    Group,
    OneOrMore,
    CaselessLiteral,
    alphas,
    nums,
    Optional,
    Combine,
    Literal,
    Word,
    QuotedString,
    Char,
    hexnums,
    ParserElement,
)

from ..constants import IDF_PATH, ALL_TARGETS


def get_defines(header_path):  # type: (Path) -> list[str]
    defines = []
    logging.debug('Reading macros from %s...', header_path)
    with open(header_path, 'r') as f:
        output = f.read()

    for line in output.split('\n'):
        line = line.strip()
        if len(line):
            defines.append(line)

    return defines


def parse_define(define_line):  # type: (str) -> type[ParserElement]

    # Group for parsing literal suffix of a numbers, e.g. 100UL
    literal_symbol = Group(CaselessLiteral('L') | CaselessLiteral('U'))
    literal_suffix = OneOrMore(literal_symbol)

    # Define name
    name = Word(alphas, alphas + nums + '_')

    # Define value, either a hex, int or a string
    hex_value = Combine(
        Literal('0x') + Word(hexnums) + Optional(literal_suffix).suppress()
    )('hex_value')
    int_value = (
        Word(nums)('int_value')
        + ~Char('.')
        + Optional(literal_suffix)('literal_suffix')
    )
    str_value = QuotedString('"')('str_value')

    # Remove optional parenthesis around values
    value = (
        Optional('(').suppress()
        + (hex_value ^ int_value ^ str_value)('value')
        + Optional(')').suppress()
    )

    expr = '#define' + Optional(name)('name') + Optional(value)
    res = expr.parseString(define_line)

    return res


class SocHeader(dict):
    def __init__(self, target):  # type: (str) -> None
        if target != 'linux':
            soc_header_dict = self._parse_soc_header(target)
        else:
            soc_header_dict = {}

        super().__init__(**soc_header_dict)

    @staticmethod
    def _parse_soc_header(target):  # type: (str) -> dict[str, any]
        soc_headers_dir = IDF_PATH / 'components' / 'soc' / target / 'include' / 'soc'

        if not soc_headers_dir.is_dir():
            logging.debug('No soc header files folder: %s', soc_headers_dir.resolve())
            return {}

        output_dict = {}
        for soc_header_file in soc_headers_dir.glob('*_caps.h'):
            for line in get_defines(soc_header_file):
                try:
                    res = parse_define(line)
                except ParseException:
                    logging.debug('Failed to parse: %s', line)
                    continue

                if 'str_value' in res:
                    output_dict[res.name] = res.str_value
                elif 'int_value' in res:
                    output_dict[res.name] = int(res.int_value)
                elif 'hex_value' in res:
                    output_dict[res.name] = int(res.hex_value, 16)

        return output_dict


SOC_HEADERS = {target: SocHeader(target) for target in ALL_TARGETS}
