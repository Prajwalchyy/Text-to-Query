"""
Unit tests for Pandas AST Security Guardrail (pandas_guard.py).

Validates AST NodeVisitor sandboxing: blocking imports, loops, function definitions,
dangerous built-ins (open, eval, exec, system), dunder attributes, and enforcing
result_df assignment.
"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from guardrails.pandas_guard import (
    validate_pandas_code,
    clean_code_markdown,
    PandasASTGuardrail,
    PandasSecurityViolation,
    FORBIDDEN_PANDAS_CALLS,
    FORBIDDEN_PANDAS_MODULES,
)


def test_valid_pandas_code():
    code = "result_df = df[df['TotalAmount'] > 500].groupby('Region')['TotalAmount'].sum().reset_index()"
    is_safe, err = validate_pandas_code(code)
    assert is_safe is True
    assert err is None


def test_markdown_fence_stripping():
    markdown_code = """```python
result_df = df.sort_values('TotalAmount', ascending=False).head(5)
```"""
    is_safe, err = validate_pandas_code(markdown_code)
    assert is_safe is True
    assert err is None


def test_forbidden_imports_blocked():
    bad_codes = [
        "import os\nresult_df = df",
        "import sys\nresult_df = df",
        "from pathlib import Path\nresult_df = df",
        "from subprocess import Popen\nresult_df = df",
    ]
    for code in bad_codes:
        is_safe, err = validate_pandas_code(code)
        assert is_safe is False
        assert "forbidden" in err.lower()
        assert "import" in err.lower()


def test_forbidden_calls_and_builtins_blocked():
    bad_codes = [
        "open('passwords.txt', 'r')",
        "eval('__import__(\"os\").system(\"calc\")')",
        "exec('print(1)')",
        "result_df = df.to_pickle('evil.pkl')",
    ]
    for code in bad_codes:
        is_safe, err = validate_pandas_code(code)
        assert is_safe is False
        assert "forbidden" in err.lower()


def test_forbidden_structures_blocked():
    # While loop
    code_while = "while True:\n    pass\nresult_df = df"
    is_safe_w, err_w = validate_pandas_code(code_while)
    assert is_safe_w is False
    assert "while loops are forbidden" in err_w

    # Function def
    code_func = "def foo():\n    return 1\nresult_df = df"
    is_safe_f, err_f = validate_pandas_code(code_func)
    assert is_safe_f is False
    assert "function definitions are disallowed" in err_f.lower()

    # Class def
    code_class = "class Bad:\n    pass\nresult_df = df"
    is_safe_c, err_c = validate_pandas_code(code_class)
    assert is_safe_c is False
    assert "class definitions are disallowed" in err_c.lower()

    # Del statement
    code_del = "del df\nresult_df = None"
    is_safe_d, err_d = validate_pandas_code(code_del)
    assert is_safe_d is False
    assert "del statements are disallowed" in err_d.lower()


def test_dunder_attributes_blocked():
    bad_codes = [
        "result_df = df.__class__",
        "result_df = df.__subclasses__()",
    ]
    for code in bad_codes:
        is_safe, err = validate_pandas_code(code)
        assert is_safe is False
        assert "dunder attribute" in err.lower()


def test_result_df_enforcement():
    # Without result_df, enforcement triggers
    code_no_result = "df.head(5)"
    is_safe, err = validate_pandas_code(code_no_result, enforce_result_df=True)
    assert is_safe is False
    assert "must assign output DataFrame to 'result_df'" in err

    # Without enforcement, simple expression is safe
    is_safe_no_enf, err_no_enf = validate_pandas_code(code_no_result, enforce_result_df=False)
    assert is_safe_no_enf is True
    assert err_no_enf is None

    # Incorrect assignment target
    code_wrong_var = "temp_df = df.head(5)"
    is_safe_wrong, err_wrong = validate_pandas_code(code_wrong_var, enforce_result_df=True)
    assert is_safe_wrong is False
    assert "must assign output DataFrame to 'result_df'" in err_wrong


def test_empty_and_syntax_error():
    is_safe_empty, err_empty = validate_pandas_code("")
    assert is_safe_empty is False
    assert "empty" in err_empty.lower()

    is_safe_syntax, err_syntax = validate_pandas_code("result_df = df[")
    assert is_safe_syntax is False
    assert "Syntax Error" in err_syntax

