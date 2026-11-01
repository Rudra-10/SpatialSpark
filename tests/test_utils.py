"""Tests for app/utils.py — validate_python_code()."""
import pytest
from app.utils import validate_python_code


def test_valid_code_returns_true():
    assert validate_python_code("def foo():\n    return 42") is True


def test_empty_string_is_valid():
    assert validate_python_code("") is True


def test_syntax_error_returns_false():
    assert validate_python_code("def foo(:\n    pass") is False


def test_invalid_indentation_returns_false():
    assert validate_python_code("if True:\nno_indent()") is False


def test_multiline_valid_script():
    code = (
        "import math\n"
        "def get_next_action():\n"
        "    return math.sqrt(4)\n"
    )
    assert validate_python_code(code) is True

