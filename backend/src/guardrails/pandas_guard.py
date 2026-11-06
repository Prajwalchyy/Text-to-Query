"""
Pandas AST Security Guardrail (Stateless Pure Functional).

Implements strict Abstract Syntax Tree (AST) inspection of Python/Pandas code:
  - Prohibits imports, loops, class/function definitions, del statements.
  - Blocks dangerous system built-ins and execution calls (eval, exec, open, system, popen).
  - Blocks access to dangerous system modules (os, sys, subprocess, socket, requests).
  - Prohibits dunder attribute access (__class__, __subclasses__, etc.).
  - Enforces assignment of final query output to 'result_df'.

Zero-state pure functional architecture replacing legacy backend/src/F14_pandas_guardrails.py.
"""

import ast
import re
from typing import NamedTuple, Optional, Set, Tuple


class PandasSecurityViolation(Exception):
    """Raised when Python/Pandas code violates AST security constraints."""
    pass


class PandasValidationResult(NamedTuple):
    """Immutable validation result for Pandas code."""

    is_valid: bool
    error: Optional[str]


FORBIDDEN_PANDAS_CALLS: Set[str] = {
    "eval",
    "exec",
    "open",
    "compile",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "system",
    "popen",
    "spawn",
    "fork",
    "to_pickle",
    "read_pickle",
}

FORBIDDEN_PANDAS_MODULES: Set[str] = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "builtins",
    "importlib",
    "pickle",
    "ctypes",
    "pty",
    "commands",
}


class PandasASTGuardrail(ast.NodeVisitor):
    """
    AST visitor inspecting Python/Pandas code before execution for defense-in-depth.
    """

    def __init__(
        self,
        forbidden_calls: Optional[Set[str]] = None,
        forbidden_modules: Optional[Set[str]] = None,
    ):
        self.forbidden_calls = forbidden_calls or FORBIDDEN_PANDAS_CALLS
        self.forbidden_modules = forbidden_modules or FORBIDDEN_PANDAS_MODULES
        self.violations: list[str] = []
        self.assigned_vars: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        self.violations.append("import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.violations.append("from ... import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.violations.append("while loops are forbidden to prevent infinite execution loops.")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.violations.append(
            "Custom function definitions are disallowed; use idiomatic Pandas expressions."
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.violations.append("Async function definitions are disallowed.")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.violations.append("Class definitions are disallowed.")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        self.violations.append("del statements are disallowed.")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assigned_vars.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.assigned_vars.add(elt.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.assigned_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        # Support walrus operator (result_df := ...)
        if isinstance(node.target, ast.Name):
            self.assigned_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct function call name (e.g. open('foo'))
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.forbidden_calls:
                self.violations.append(f"Calling dangerous function '{func_name}()' is forbidden.")
        # Check attribute/method calls (e.g. os.system() or df.to_pickle())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.forbidden_calls:
                self.violations.append(f"Calling attribute/method '{attr_name}()' is forbidden.")

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.forbidden_modules:
            self.violations.append(f"Accessing module '{node.id}' is strictly forbidden.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(f"Accessing dunder attribute '{node.attr}' is forbidden.")
        self.generic_visit(node)


def clean_code_markdown(code: str) -> str:
    """Removes markdown code fences from LLM output."""
    clean = code.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:python|py)?\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
    return clean.strip()


def validate_pandas_code(
    code: str,
    enforce_result_df: bool = True,
    forbidden_calls: Optional[Set[str]] = None,
    forbidden_modules: Optional[Set[str]] = None,
) -> PandasValidationResult:
    """
    Validates Python/Pandas code through AST parsing and security visitor.
    
    Args:
        code: Raw Python/Pandas code snippet.
        enforce_result_df: When True, requires explicit assignment to `result_df`.
        forbidden_calls: Optional custom override of forbidden function/method names.
        forbidden_modules: Optional custom override of forbidden module names.
        
    Returns:
        PandasValidationResult(is_valid: bool, error: Optional[str])
        Can be unpacked as 2 items: `is_safe, err = validate_pandas_code(...)`.
    """
    clean_code = clean_code_markdown(code) if code else ""
    if not clean_code:
        return PandasValidationResult(False, "Code string is empty.")

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return PandasValidationResult(False, f"Python Syntax Error: {str(e)}")

    visitor = PandasASTGuardrail(
        forbidden_calls=forbidden_calls,
        forbidden_modules=forbidden_modules,
    )
    visitor.visit(tree)

    # 1. Report dangerous security violations first
    if visitor.violations:
        return PandasValidationResult(
            False,
            "Security Guardrail Rejection: " + "; ".join(visitor.violations),
        )

    # 2. Enforce output assignment to result_df if requested
    if enforce_result_df and "result_df" not in visitor.assigned_vars:
        return PandasValidationResult(
            False,
            "Security Guardrail Rejection: Code must assign output DataFrame to 'result_df'.",
        )

    return PandasValidationResult(True, None)

