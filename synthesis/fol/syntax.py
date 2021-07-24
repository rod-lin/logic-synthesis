"""
Syntax of many-sorted first-order logic
"""

from __future__ import annotations

from typing import Tuple, Union, Mapping, Set
from dataclasses import dataclass
from abc import ABC, abstractmethod

from synthesis import smt

from .language import BaseAST, Sort, FunctionSymbol, RelationSymbol, Language
from .semantics import Structure

from synthesis.template import Template


class Term(BaseAST, Template["Term"], ABC):
    @abstractmethod
    def substitute(self, substitution: Mapping[Variable, Term]) -> Term: ...

    @abstractmethod
    def get_free_variables(self) -> Set[Variable]: ...

    @abstractmethod
    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm: ...

    def equals(self, value: Term) -> smt.SMTTerm:
        raise NotImplementedError()


class Formula(BaseAST, Template["Formula"], ABC):
    @abstractmethod
    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula: ...

    @abstractmethod
    def get_free_variables(self) -> Set[Variable]: ...

    @abstractmethod
    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm: ...

    def equals(self, value: Formula) -> smt.SMTTerm:
        raise NotImplementedError()

    def quantify_all_free_variables(self) -> Formula:
        free_vars = tuple(self.get_free_variables())
        formula = self

        for var in free_vars:
            formula = UniversalQuantification(var, formula)

        return formula


@dataclass(frozen=True)
class Variable(Term):
    name: str
    sort: Sort

    def __str__(self) -> str:
        return f"{self.name}:{self.sort}"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Term:
        if self in substitution:
            return substitution[self]
        return self

    def get_free_variables(self) -> Set[Variable]:
        return { self }

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        assert self in valuation, \
               f"unable to interpret {self}"
        return valuation[self]
    
    def get_constraint(self) -> smt.SMTTerm:
        return smt.TRUE()

    def get_from_smt_model(self, model: smt.SMTModel) -> Term:
        return self


@dataclass(frozen=True)
class Application(Term):
    function_symbol: FunctionSymbol
    arguments: Tuple[Term, ...]

    def __str__(self) -> str:
        if len(self.arguments) == 0: return self.function_symbol.name
        argument_string = ", ".join((str(arg) for arg in self.arguments))
        return f"{self.function_symbol.name}({argument_string})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Term:
        return Application(self.function_symbol, tuple(argument.substitute(substitution) for argument in self.arguments))

    def get_free_variables(self) -> Set[Variable]:
        free_vars = set()
        for argument in self.arguments:
            free_vars.update(argument.get_free_variables())
        return free_vars

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return structure.interpret_function(
            self.function_symbol,
            *(argument.interpret(structure, valuation) for argument in self.arguments),
        )

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(*(argument.get_constraint() for argument in self.arguments))

    def get_from_smt_model(self, model: smt.SMTModel) -> Term:
        return self


@dataclass
class Verum(Formula):
    def __str__(self) -> str:
        return "⊤"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return self

    def get_free_variables(self) -> Set[Variable]:
        return set()

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.TRUE()

    def get_constraint(self) -> smt.SMTTerm:
        return smt.TRUE()

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return self


@dataclass
class Falsum(Formula):
    def __str__(self) -> str:
        return "⊥"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return self

    def get_free_variables(self) -> Set[Variable]:
        return set()

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.FALSE()

    def get_constraint(self) -> smt.SMTTerm:
        return smt.TRUE()

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return self


@dataclass(frozen=True)
class RelationApplication(Formula):
    relation_symbol: RelationSymbol
    arguments: Tuple[Term, ...]

    def __str__(self) -> str:
        argument_string = ", ".join((str(arg) for arg in self.arguments))
        return f"{self.relation_symbol.name}({argument_string})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return RelationApplication(self.relation_symbol, tuple(argument.substitute(substitution) for argument in self.arguments))

    def get_free_variables(self) -> Set[Variable]:
        free_vars = set()
        for argument in self.arguments:
            free_vars.update(argument.get_free_variables())
        return free_vars

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return structure.interpret_relation(
            self.relation_symbol,
            *(argument.interpret(structure, valuation) for argument in self.arguments),
        )

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(*(argument.get_constraint() for argument in self.arguments))

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return RelationApplication(
            self.relation_symbol,
            tuple(argument.get_from_smt_model(model) for argument in self.arguments),
        )


AtomicFormula = Union[Verum, Falsum, RelationApplication]


@dataclass(frozen=True)
class Conjunction(Formula):
    left: Formula
    right: Formula

    def __str__(self) -> str:
        return f"({self.left} /\\ {self.right})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return Conjunction(
            self.left.substitute(substitution),
            self.right.substitute(substitution),
        )

    def get_free_variables(self) -> Set[Variable]:
        return self.left.get_free_variables().union(self.right.get_free_variables())

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.And(
            self.left.interpret(structure, valuation),
            self.right.interpret(structure, valuation),
        )

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.left.get_constraint(), self.right.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return Conjunction(
            self.left.get_from_smt_model(model),
            self.right.get_from_smt_model(model),
        )


@dataclass(frozen=True)
class Disjunction(Formula):
    left: Formula
    right: Formula

    def __str__(self) -> str:
        return f"({self.left} \\/ {self.right})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return Disjunction(
            self.left.substitute(substitution),
            self.right.substitute(substitution),
        )

    def get_free_variables(self) -> Set[Variable]:
        return self.left.get_free_variables().union(self.right.get_free_variables())

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.Or(
            self.left.interpret(structure, valuation),
            self.right.interpret(structure, valuation),
        )

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.left.get_constraint(), self.right.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return Disjunction(
            self.left.get_from_smt_model(model),
            self.right.get_from_smt_model(model),
        )


@dataclass(frozen=True)
class Negation(Formula):
    formula: Formula

    def __str__(self) -> str:
        return f"not {self.formula}"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return Negation(self.formula.substitute(substitution))

    def get_free_variables(self) -> Set[Variable]:
        return self.formula.get_free_variables()

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.Not(self.formula.interpret(structure, valuation))

    def get_constraint(self) -> smt.SMTTerm:
        return self.formula.get_constraint()

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return Negation(self.formula.get_from_smt_model(model))


@dataclass(frozen=True)
class Implication(Formula):
    left: Formula
    right: Formula

    def __str__(self) -> str:
        return f"({self.left} -> {self.right})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return Implication(
            self.left.substitute(substitution),
            self.right.substitute(substitution),
        )

    def get_free_variables(self) -> Set[Variable]:
        return self.left.get_free_variables().union(self.right.get_free_variables())

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.Implies(
            self.left.interpret(structure, valuation),
            self.right.interpret(structure, valuation),
        )

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.left.get_constraint(), self.right.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return Implication(
            self.left.get_from_smt_model(model),
            self.right.get_from_smt_model(model),
        )


@dataclass(frozen=True)
class Equivalence(Formula):
    left: Formula
    right: Formula

    def __str__(self) -> str:
        return f"({self.left} <-> {self.right})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        return Equivalence(
            self.left.substitute(substitution),
            self.right.substitute(substitution),
        )

    def get_free_variables(self) -> Set[Variable]:
        return self.left.get_free_variables().union(self.right.get_free_variables())

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        return smt.Iff(
            self.left.interpret(structure, valuation),
            self.right.interpret(structure, valuation),
        )
    
    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.left.get_constraint(), self.right.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return Equivalence(
            self.left.get_from_smt_model(model),
            self.right.get_from_smt_model(model),
        )


@dataclass(frozen=True)
class UniversalQuantification(Formula):
    variable: Variable
    body: Formula

    def __str__(self) -> str:
        return f"(forall {self.variable}. {self.body})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        if self.variable in substitution:
            substitution = { k: v for k, v in substitution.items() if k != self.variable }
        return UniversalQuantification(self.variable, self.body.substitute(substitution))

    def get_free_variables(self) -> Set[Variable]:
        return self.body.get_free_variables().difference({ self.variable })

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        carrier = structure.interpret_sort(self.variable.sort)
        smt_var = smt.FreshSymbol(carrier.get_smt_sort())
        interp = self.body.interpret(structure, { **valuation, self.variable: smt_var })
        return carrier.universally_quantify(smt_var, interp)

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.variable.get_constraint(), self.body.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return UniversalQuantification(
            self.variable,
            self.body.get_from_smt_model(model),
        )


@dataclass(frozen=True)
class ExistentialQuantification(Formula):
    variable: Variable
    body: Formula

    def __str__(self) -> str:
        return f"(exists {self.variable}. {self.body})"

    def substitute(self, substitution: Mapping[Variable, Term]) -> Formula:
        if self.variable in substitution:
            substitution = { k: v for k, v in substitution.items() if k != self.variable }
        return ExistentialQuantification(self.variable, self.body.substitute(substitution))

    def get_free_variables(self) -> Set[Variable]:
        return self.body.get_free_variables().difference({ self.variable })

    def interpret(self, structure: Structure, valuation: Mapping[Variable, smt.SMTTerm]) -> smt.SMTTerm:
        carrier = structure.interpret_sort(self.variable.sort)
        smt_var = smt.FreshSymbol(carrier.get_smt_sort())
        interp = self.body.interpret(structure, { **valuation, self.variable: smt_var })
        return carrier.existentially_quantify(smt_var, interp)

    def get_constraint(self) -> smt.SMTTerm:
        return smt.And(self.variable.get_constraint(), self.body.get_constraint())

    def get_from_smt_model(self, model: smt.SMTModel) -> Formula:
        return ExistentialQuantification(
            self.variable,
            self.body.get_from_smt_model(model),
        )
