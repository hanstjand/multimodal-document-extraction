"""AST-restricted evaluation of agent-written graph expressions (CP-4.4; R13 [RECONSTRUCTED]).

The LAD-RAG agent (Fig. 12) writes a Python **expression** over ``doc_graph`` for ``graph_filter``,
e.g. ``[(node_id, node) for node_id, node in doc_graph.nodes(data=True) if node.get('type') ==
'figure']`` (Fig. 5), and calls ``get_community_for_node(node_id, doc_graph)`` for
``graph_contextualize`` (Fig. 6). This module evaluates such expressions safely:

1. **Static check** (before anything runs): the text must parse as one expression (``mode="eval"``);
   only allow-listed AST node types; no names or attributes starting with ``_``; attribute access only
   for the allow-listed method names in :data:`ALLOWED_ATTRIBUTES`; no ``**``, ``*``, shifts, walrus,
   f-strings, ``await``/``yield``; integer constants ``|x| <= 10**6``, strings ``<= 1000`` characters;
   limited expression size and nesting.
2. **Restricted namespace**: builtins limited to :data:`SAFE_BUILTINS` (no ``open``, ``__import__``,
   ``getattr``, ``eval``, ``type`` …); ``doc_graph`` is a :class:`SafeGraphView` — a frozen, read-only
   facade (plain-data snapshots of nodes and edges, canonical order) that exposes no NetworkX object.
3. **Resource guard**: wall-clock timeout ``agent.code_timeout_s`` (default 10 s) enforced by a trace
   function on Python-level execution (loops, comprehensions, lambdas); results larger than
   ``max_result_items`` are rejected. Generators are materialized inside the guard. A single C-level
   operation cannot be interrupted by the trace function; the static rules (no ``*``/``**``/shifts,
   bounded constants) and a numbers-only ``sum`` remove the known ways to make one explode. The
   threat model is accidental runaway code from our own agent model, not a hostile user; absolute
   isolation would need a separate process (not required by R13).

Results are deterministic: nodes/edges/neighbours are always listed in node ID order.
There is no file, network or process access in the namespace. Errors raise :class:`QueryError`
(the agent loop reports them as ``ERROR: …`` observations, R11).
"""

import ast
import copy
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from multimodal_document_extraction.studies.ladrag.graph_retrieval import (
    GraphIndex,
    UnknownNodeError,
    node_order_key,
)

DEFAULT_TIMEOUT_S = 10.0  # IMPLEMENTATION_SPEC §6 agent.code_timeout_s (R13)
DEFAULT_MAX_RESULT_ITEMS = 100_000
MAX_EXPRESSION_CHARS = 4000
MAX_AST_NODES = 500
MAX_INT_CONSTANT = 10**6
MAX_STR_CONSTANT = 1000


def _numeric_sum(iterable: Any, start: float = 0) -> float:
    """``sum`` restricted to numbers (list/str concatenation via ``sum`` is quadratic C code that the
    trace-based timeout cannot interrupt)."""
    if isinstance(start, bool) or not isinstance(start, (int, float)):
        raise TypeError("sum() start must be a number")
    total = start
    for value in iterable:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("sum() accepts numbers only")
        total += value
    return total


SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
    "float": float, "int": int, "isinstance": isinstance, "len": len, "list": list, "max": max,
    "min": min, "range": range, "reversed": reversed, "round": round, "set": set,
    "sorted": sorted, "str": str, "sum": _numeric_sum, "tuple": tuple, "zip": zip,
    "True": True, "False": False, "None": None,
}  # fmt: skip

# Method names callable/readable via attribute access (on the graph facade, dicts and strings).
ALLOWED_ATTRIBUTES = frozenset(
    {
        # SafeGraphView
        "nodes", "edges", "neighbors", "has_node", "degree", "number_of_nodes", "number_of_edges",
        # read-only dict methods
        "get", "keys", "values", "items",
        # read-only str methods
        "lower", "upper", "strip", "lstrip", "rstrip", "startswith", "endswith", "split", "isdigit",
        "count", "find", "casefold",
    }
)  # fmt: skip

_ALLOWED_NODES = (
    ast.Expression, ast.Expr,
    # literals and containers
    ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict,
    # names, attributes, subscripts
    ast.Name, ast.Load, ast.Store, ast.Attribute, ast.Subscript, ast.Slice,
    # operators
    ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add, ast.Sub, ast.Div, ast.FloorDiv, ast.Mod,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.IfExp,
    # calls, comprehensions, lambdas
    ast.Call, ast.keyword, ast.Starred,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.Lambda, ast.arguments, ast.arg,
)  # fmt: skip


class QueryError(Exception):
    """An expression was rejected or failed (message is safe to show to the agent)."""


class QueryTimeoutError(QueryError):
    """The expression exceeded the time limit."""


# --- read-only graph facade ------------------------------------------------------------------------


class _NodesAccessor:
    """``doc_graph.nodes(data=False)`` → list; ``doc_graph.nodes[node_id]`` → attribute dict copy."""

    def __init__(self, view: "SafeGraphView") -> None:
        self._view = view

    def __call__(self, data: bool = False) -> list:
        order = self._view._order
        if data:
            return [(n, copy.deepcopy(self._view._nodes[n])) for n in order]
        return list(order)

    def __getitem__(self, node_id: str) -> dict[str, Any]:
        return copy.deepcopy(self._view._node(node_id))

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._view._order))

    def __len__(self) -> int:
        return len(self._view._order)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._view._nodes


class SafeGraphView:
    """Frozen, read-only, NetworkX-like facade for agent expressions (plain data only)."""

    def __init__(self, index: GraphIndex) -> None:
        self._order = tuple(index.nodes_in_order())
        self._nodes = {n: copy.deepcopy(index.node(n)) for n in self._order}
        self._edges = tuple(index.edges())
        self._adjacency: dict[str, list[str]] = {n: [] for n in self._order}
        for a, b, _ in self._edges:
            self._adjacency[a].append(b)
            self._adjacency[b].append(a)
        for n in self._adjacency:
            self._adjacency[n].sort(key=node_order_key)
        self.nodes = _NodesAccessor(self)
        self.doc_id = index.doc_id

    def _node(self, node_id: Any) -> dict[str, Any]:
        if not isinstance(node_id, str) or node_id not in self._nodes:
            raise UnknownNodeError(f"unknown node {node_id!r}")
        return self._nodes[node_id]

    def edges(self, data: bool = False) -> list:
        if data:
            return [(a, b, copy.deepcopy(d)) for a, b, d in self._edges]
        return [(a, b) for a, b, _ in self._edges]

    def neighbors(self, node_id: str) -> list[str]:
        self._node(node_id)
        return list(self._adjacency[node_id])

    def has_node(self, node_id: Any) -> bool:
        return isinstance(node_id, str) and node_id in self._nodes

    def degree(self, node_id: str) -> int:
        self._node(node_id)
        return len(self._adjacency[node_id])

    def number_of_nodes(self) -> int:
        return len(self._order)

    def number_of_edges(self) -> int:
        return len(self._edges)


# --- static validation -----------------------------------------------------------------------------


def validate_expression(expression: str) -> ast.Expression:
    """Parse and statically check an agent expression; raise :class:`QueryError` if disallowed."""
    if not isinstance(expression, str) or not expression.strip():
        raise QueryError("empty expression")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise QueryError(f"expression longer than {MAX_EXPRESSION_CHARS} characters")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise QueryError(f"not a single Python expression: {exc.msg}") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise QueryError(f"expression too large ({len(nodes)} > {MAX_AST_NODES} syntax nodes)")
    for node in nodes:
        if not isinstance(node, _ALLOWED_NODES):
            raise QueryError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise QueryError(f"disallowed name {node.id!r}")
        if isinstance(node, ast.arg) and node.arg.startswith("_"):
            raise QueryError(f"disallowed name {node.arg!r}")
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith("_") or node.attr not in ALLOWED_ATTRIBUTES
        ):
            raise QueryError(f"disallowed attribute {node.attr!r}")
        if isinstance(node, ast.keyword) and (node.arg is None or node.arg.startswith("_")):
            raise QueryError("disallowed keyword argument")
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, int) and abs(value) > MAX_INT_CONSTANT:
                raise QueryError(f"integer constant larger than {MAX_INT_CONSTANT}")
            if isinstance(value, str) and len(value) > MAX_STR_CONSTANT:
                raise QueryError(f"string constant longer than {MAX_STR_CONSTANT}")
            if not isinstance(value, (int, float, str)):
                raise QueryError(f"disallowed constant of type {type(value).__name__}")
        if isinstance(node, ast.comprehension) and node.is_async:
            raise QueryError("disallowed syntax: async comprehension")
    return tree


# --- guarded evaluation ----------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphQueryEngine:
    """Evaluates agent expressions against one document graph (frozen snapshot)."""

    view: SafeGraphView
    index: GraphIndex
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_result_items: int = DEFAULT_MAX_RESULT_ITEMS

    @classmethod
    def for_graph(cls, index: GraphIndex, **kwargs: Any) -> "GraphQueryEngine":
        return cls(SafeGraphView(index), index, **kwargs)

    def _namespace(self) -> dict[str, Any]:
        index = self.index

        def get_community_for_node(node_id: str, doc_graph: Any = None) -> list:
            # [PAPER-EXACT] signature; the second argument is accepted and ignored (always this graph)
            return index.get_community_for_node(node_id)

        return {
            "__builtins__": dict(SAFE_BUILTINS),
            "doc_graph": self.view,
            "get_community_for_node": get_community_for_node,
        }

    def evaluate(self, expression: str) -> Any:
        """Evaluate one expression; returns plain data (generators/iterators are materialized)."""
        tree = validate_expression(expression)
        code = compile(tree, "<graph_query>", "eval")
        deadline = time.monotonic() + self.timeout_s

        def tracer(frame: Any, event: str, arg: Any) -> Any:
            if time.monotonic() > deadline:
                raise QueryTimeoutError(f"expression exceeded {self.timeout_s:g} s")
            return tracer

        previous = sys.gettrace()
        sys.settrace(tracer)
        try:
            result = eval(code, self._namespace())  # statically validated above
            if not isinstance(result, _PLAIN_TYPES) and hasattr(result, "__iter__"):
                result = list(result)  # materialize generators inside the guard
        except QueryError:
            raise
        except UnknownNodeError as exc:
            raise QueryError(str(exc).strip("'\"")) from None
        except Exception as exc:  # noqa: BLE001 — any runtime error becomes an agent-visible error
            raise QueryError(f"{type(exc).__name__}: {exc}") from None
        finally:
            sys.settrace(previous)
        if isinstance(result, _CONTAINERS) and len(result) > self.max_result_items:
            raise QueryError(f"result has more than {self.max_result_items} items")
        return result


_CONTAINERS = (list, tuple, dict, set, frozenset)
_PLAIN_TYPES = (*_CONTAINERS, str, int, float, bool, type(None))
