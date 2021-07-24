"""
Many-sorted language
"""

from __future__ import annotations

from typing import Tuple, Optional
from dataclasses import dataclass

from synthesis import smt


class BaseAST: ...


@dataclass(frozen=True)
class Sort(BaseAST):
    name: str
    smt_hook: Optional[smt.SMTSort] = None

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class FunctionSymbol(BaseAST):
    input_sorts: Tuple[Sort, ...]
    output_sort: Sort
    name: str
    smt_hook: Optional[smt.SMTFunction] = None # if set, the function is interpreted as an SMT function


@dataclass(frozen=True)
class RelationSymbol(BaseAST):
    input_sorts: Tuple[Sort, ...]
    name: str
    smt_hook: Optional[smt.SMTFunction] = None # if set, the function is interpreted as an SMT function


@dataclass(frozen=True)
class Language:
    """
    A many-sorted language
    """
    sorts: Tuple[Sort, ...]
    function_symbols: Tuple[FunctionSymbol, ...]
    relation_symbols: Tuple[RelationSymbol, ...]

    # TODO: add dict for sorts/functions/relations

    def get_sort(self, name: str) -> Optional[Sort]:
        for sort in self.sorts:
            if sort.name == name:
                return sort
        return None

    def get_function_symbol(self, name: str) -> Optional[FunctionSymbol]:
        for symbol in self.function_symbols:
            if symbol.name == name:
                return symbol
        return None

    def get_relation_symbol(self, name: str) -> Optional[RelationSymbol]:
        for symbol in self.relation_symbols:
            if symbol.name == name:
                return symbol
        return None

    def get_max_function_arity(self) -> int:
        return max(tuple(len(symbol.input_sorts) for symbol in self.function_symbols) + (0,))

    def get_max_relation_arity(self) -> int:
        return max(tuple(len(symbol.input_sorts) for symbol in self.relation_symbols) + (0,))

    def expand(self, other: Language) -> Language:
        for sort in other.sorts:
            assert sort not in self.sorts, f"duplicate sort {sort}"

        for function_symbol in other.function_symbols:
            assert function_symbol not in self.function_symbols, f"duplicate function symbol {function_symbol}"

        for relation_symbol in other.relation_symbols:
            assert relation_symbol not in self.relation_symbols, f"duplicate relation symbol {relation_symbol}"

        return Language(
            self.sorts + other.sorts,
            self.function_symbols + other.function_symbols,
            self.relation_symbols + other.relation_symbols,
        )
