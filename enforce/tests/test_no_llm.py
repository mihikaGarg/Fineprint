import ast
from pathlib import Path

ENFORCE_DIR = Path(__file__).resolve().parents[1]


def test_enforce_never_imports_llm() -> None:
    for path in ENFORCE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith(("shared.llm", "anthropic", "openai")), (
                    f"{path} imports {name}"
                )
