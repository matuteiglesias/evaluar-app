from pathlib import Path


def test_python_package_directories_are_valid_identifiers():
    root = Path(__file__).resolve().parents[1]
    package_directories = {
        init.parent.relative_to(root)
        for init in root.rglob("__init__.py")
        if ".venv" not in init.parts
    }
    assert package_directories
    for directory in package_directories:
        assert all(part.isidentifier() for part in directory.parts), directory


def test_evaluar_is_an_importable_src_package():
    import evaluar

    assert Path(evaluar.__file__).resolve().name == "__init__.py"
