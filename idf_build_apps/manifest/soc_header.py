# SPDX-FileCopyrightText: 2022-2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import typing as t
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

LOGGER = logging.getLogger(__name__)

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
_value = Optional('(').suppress() + MatchFirst([_hex_value, _str_value, _int_value])('value') + Optional(')').suppress()

_define_expr = '#define' + Optional(_name)('name') + Optional(_value)


def get_defines(header_path: Path) -> t.List[str]:
    defines = []
    LOGGER.debug('Reading macros from %s...', header_path)
    with open(str(header_path)) as f:
        output = f.read()

    for line in output.split('\n'):
        line = line.strip()
        if len(line):
            defines.append(line)

    return defines


def parse_define(define_line: str) -> ParseResults:
    res = _define_expr.parseString(define_line)

    return res


class SocHeader(dict):
    CAPS_HEADER_FILEPATTERN = '*_caps.h'

    def __init__(self, target: str) -> None:
        if target != 'linux':
            soc_header_dict = self._parse_soc_header(target)
        else:
            soc_header_dict = {}

        super().__init__(**soc_header_dict)

    @staticmethod
    def _get_dir_from_candidates(candidates: t.List[Path]) -> t.Optional[Path]:
        for d in candidates:
            if not d.is_dir():
                LOGGER.debug('folder "%s" not found. Skipping...', d.absolute())
            else:
                return d

        return None

    @classmethod
    def _parse_soc_header(cls, target: str) -> t.Dict[str, t.Any]:
        soc_headers_dir = cls._get_dir_from_candidates(
            [
                # other branches
                IDF_PATH / 'components' / 'soc' / target / 'include' / 'soc',
                # release/v4.2
                IDF_PATH / 'components' / 'soc' / 'soc' / target / 'include' / 'soc',
            ]
        )
        esp_rom_headers_dir = cls._get_dir_from_candidates(
            [
                IDF_PATH / 'components' / 'esp_rom' / target,
            ]
        )

        header_files = []
        if soc_headers_dir:
            header_files += list(soc_headers_dir.glob(cls.CAPS_HEADER_FILEPATTERN))
        if esp_rom_headers_dir:
            header_files += list(esp_rom_headers_dir.glob(cls.CAPS_HEADER_FILEPATTERN))

        output_dict = {}
        for f in header_files:
            for line in get_defines(f):
                try:
                    res = parse_define(line)
                except ParseException:
                    LOGGER.debug('Failed to parse: %s', line)
                    continue

                if 'str_value' in res:
                    output_dict[res.name] = res.str_value
                elif 'int_value' in res:
                    output_dict[res.name] = int(res.int_value)
                elif 'hex_value' in res:
                    output_dict[res.name] = int(res.hex_value, 16)

        return output_dict


SOC_HEADERS: t.Dict[str, SocHeader] = {target: SocHeader(target) for target in ALL_TARGETS}
