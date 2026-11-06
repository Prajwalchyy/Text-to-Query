import ast
import re
from typing import Tuple, Optional, Set


class PandasSecurityViolation(Exception):
    """Raised when Python/Pandas code violates AST security constraints."""
    pass


class PandasASTGuardrail(ast.NodeVisitor):
    """
    Strict AST visitor that inspects Python code before execution to ensure
    defense-in-depth against code injection, unauthorized file access, or process execution.
    """

    FORBIDDEN_CALLS: Set[str] = {
        "eval", "exec", "open", "compile", "__import__", "globals", "locals",
        "getattr", "setattr", "delattr", "system", "popen", "spawn", "fork"
    }

    FORBIDDEN_MODULES: Set[str] = {
        "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
        "pathlib", "builtins", "importlib", "pickle", "ctypes", "pty", "commands"
    }

    def __init__(self):
        self.violations = []

    def visit_Import(self, node):
        self.violations.append("import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.violations.append("from ... import statements are strictly forbidden.")
        self.generic_visit(node)

    def visit_While(self, node):
        self.violations.append("while loops are forbidden to prevent infinite execution loops.")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Allow simple helper lambda/funcs or disallow complex definitions
        self.violations.append("Custom function definitions are disallowed; use idiomatic Pandas expressions.")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.violations.append("Async function definitions are disallowed.")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.violations.append("Class definitions are disallowed.")
        self.generic_visit(node)

    def visit_Delete(self, node):
        self.violations.append("del statements are disallowed.")
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check direct function call name (e.g. open('foo'))
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.FORBIDDEN_CALLS:
                self.violations.append(f"Calling dangerous function '{func_name}()' is forbidden.")
        # Check method calls (e.g. os.system())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.FORBIDDEN_CALLS:
                self.violations.append(f"Calling attribute/method '{attr_name}()' is forbidden.")

        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in self.FORBIDDEN_MODULES:
            self.violations.append(f"Accessing module '{node.id}' is strictly forbidden.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(f"Accessing dunder attribute '{node.attr}' is forbidden.")
        self.generic_visit(node)


def validate_pandas_code(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validates Python/Pandas code through AST parsing and security visitor.
    Returns:
        (True, None) if code is safe to execute.
        (False, error_message) if violation is detected.
    """
    clean_code = code.strip()
    if clean_code.startswith("```"):
        clean_code = re.sub(r"^```(?:python|py)?\n?", "", clean_code)
        clean_code = re.sub(r"\n?```$", "", clean_code)
    clean_code = clean_code.strip()

    if not clean_code:
        return False, "Code string is empty."

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return False, f"Python Syntax Error: {str(e)}"

    visitor = PandasASTGuardrail()
    visitor.visit(tree)

    if visitor.violations:
        return False, "Security Guardrail Rejection: " + "; ".join(visitor.violations)

    return True, None
