import ast
import operator
import re
from typing import Any, Callable

Tool = Callable[[Any], Any]
_REGISTRY: dict[str, Tool] = {}

def register(name: str):
    def decorator(func: Tool) -> Tool:
        _REGISTRY[name] = func
        return func
    return decorator

def list_tools() -> list[dict[str, str]]:
    return [
        {"name": "math.calculate", "description": "Evaluate basic arithmetic safely."},
        {"name": "text.word_count", "description": "Count words in a string."},
        {"name": "text.uppercase", "description": "Convert text to uppercase."},
    ]

_ALLOWED_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.UAdd: operator.pos, ast.USub: operator.neg,
}

def _safe_math(expression: str) -> float | int:
    if len(expression) > 120:
        raise ValueError("Expression is too long")
    tree = ast.parse(expression, mode="eval")
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("Exponent is too large")
            result = _ALLOWED_OPERATORS[type(node.op)](left, right)
            if abs(result) > 10**15:
                raise ValueError("Result is too large")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Unsupported arithmetic expression")
    return visit(tree)

@register("math.calculate")
def calculate(value: Any) -> float | int:
    return _safe_math(str(value))

@register("text.word_count")
def word_count(value: Any) -> int:
    return len(str(value).split())

@register("text.uppercase")
def uppercase(value: Any) -> str:
    return str(value).upper()

def execute_tool(name: str, value: Any) -> Any:
    tool = _REGISTRY.get(name)
    if tool is None:
        raise ValueError(f"Tool is not registered: {name}")
    return tool(value)
