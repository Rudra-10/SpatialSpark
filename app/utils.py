import ast


def validate_python_code(code: str) -> bool:
    """Return True if `code` is syntactically valid Python; False otherwise.

    Use before any exec() on LLM-generated strings — never exec without this check.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

