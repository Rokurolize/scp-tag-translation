import ast
from pathlib import Path


ROOT = Path(__file__).parent.parent
SCRIPT_ROOT = ROOT / "scripts"


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
                if alias.name.startswith("scripts.")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if node.level:
                continue
            if module.startswith("scripts."):
                imports.add(module)
    return imports


def _imports_from(package: str) -> set[str]:
    imports: set[str] = set()
    for path in (SCRIPT_ROOT / package).rglob("*.py"):
        imports.update(_internal_imports(path))
    return imports


def test_layered_packages_keep_dependency_direction_explicit():
    domain_imports = _imports_from("domain")
    parser_imports = _imports_from("parsers")
    pipeline_imports = _imports_from("pipeline")
    infrastructure_imports = _imports_from("infrastructure")

    assert not any(
        module.startswith(("scripts.application", "scripts.pipeline", "scripts.parsers"))
        for module in domain_imports
    )
    assert not any(
        module.startswith(("scripts.application", "scripts.pipeline", "scripts.infrastructure"))
        for module in parser_imports
    )
    assert not any(
        module.startswith(("scripts.application", "scripts.parsers"))
        for module in pipeline_imports
    )
    assert infrastructure_imports <= {
        "scripts.domain.errors",
        "scripts.infrastructure.file_modes",
    }
