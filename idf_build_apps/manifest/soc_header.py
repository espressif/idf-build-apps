# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import (
    Path,
)

from pyparsing import (
    CaselessLiteral,
    Char,
    Combine,
    Group,
    Literal,
    MatchFirst,
    OneOrMore,
    Optional,
    ParseException,
    ParseResults,
    QuotedString,
    Word,
    alphas,
    hexnums,
    nums,
)

from ..constants import (
    ALL_TARGETS,
    IDF_PATH,
)

# Group for parsing literal suffix of a numbers, e.g. 100UL
_literal_symbol = Group(CaselessLiteral('L') | CaselessLiteral('U'))
_literal_suffix = OneOrMore(_literal_symbol)

# Define name
_name = Word(alphas, alphas + nums + '_')

# Define value, either a hex, int or a string
_hex_value = Combine(Literal('0x') + Word(hexnums) + Optional(_literal_suffix).suppress())('hex_value')
_str_value = QuotedString('"')('str_value')
_int_value = Word(nums)('int_value') + ~Char('.') + Optional(_literal_suffix)('literal_suffix')

# Remove optional parenthesis around values
_value = Optional('(').suppress() + MatchFirst(_hex_value | _str_value | _int_value)('value') + Optional(')').suppress()

_define_expr = '#define' + Optional(_name)('name') + Optional(_value)


def get_defines(header_path):  # type: (Path) -> list[str]
    defines = []
    logging.debug('Reading macros from %s...', header_path)
    with open(str(header_path), 'r') as f:
        output = f.read()

    for line in output.split('\n'):
        line = line.strip()
        if len(line):
            defines.append(line)

    return defines


def parse_define(define_line):  # type: (str) -> ParseResults
    res = _define_expr.parseString(define_line)

    return res


class SocHeader(dict):
    def __init__(self, target):  # type: (str) -> None
        if target != 'linux':
            soc_header_dict = self._parse_soc_header(target)
        else:
            soc_header_dict = {}

        super(SocHeader, self).__init__(**soc_header_dict)

    @staticmethod
    def _parse_soc_header(target):  # type: (str) -> dict[str, any]
        soc_headers_dir_candidates = [
            # other branches
            IDF_PATH / 'components' / 'soc' / target / 'include' / 'soc',
            # release/v4.2
            IDF_PATH / 'components' / 'soc' / 'soc' / target / 'include' / 'soc',
        ]

        # get the soc_headers_dir
        soc_headers_dir = None
        for d in soc_headers_dir_candidates:
            if not d.is_dir():
                logging.debug('No soc header files folder: %s', d.absolute())
            else:
                soc_headers_dir = d
                break

        if not soc_headers_dir:
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
