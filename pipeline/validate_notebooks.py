"""Validate notebook structure and optionally execute selected notebooks.

Dataset-dependent notebooks are not all executable in a clean CI checkout:
OULAD, EdNet, and KU Leuven files are external, licensed inputs. CI therefore
parses every notebook and executes the synthetic notebooks against a generated
fixture. A local or scheduled data-qualified run can execute the remaining
notebooks by passing their paths explicitly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def discover_notebooks(paths: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    for path in paths:
        if path.is_dir():
            discovered.extend(sorted(path.glob("*.ipynb")))
        elif path.suffix == ".ipynb":
            discovered.append(path)
        else:
            raise ValueError(f"Notebook path must be a directory or .ipynb file: {path}")
    return sorted({path.resolve() for path in discovered})


def validate_notebooks(
    paths: list[Path],
    *,
    execute: bool = False,
    output_dir: Path | None = None,
    timeout: int = 600,
) -> list[Path]:
    notebooks = discover_notebooks(paths)
    if not notebooks:
        raise ValueError("No notebooks were found")
    for notebook_path in notebooks:
        notebook = nbformat.read(notebook_path, as_version=4)
        nbformat.validate(notebook)
        if not execute:
            print(f"validated: {notebook_path}")
            continue

        client = NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(Path.cwd())}},
        )
        client.execute()
        destination = notebook_path
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            destination = output_dir / notebook_path.name
        nbformat.write(notebook, destination)
        print(f"executed: {notebook_path} -> {destination}")
    return notebooks


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or execute project notebooks")
    parser.add_argument("paths", nargs="+", type=Path, help="Notebook files or directories")
    parser.add_argument("--execute", action="store_true", help="Execute notebooks and save outputs")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    validate_notebooks(args.paths, execute=args.execute, output_dir=args.output_dir, timeout=args.timeout)


if __name__ == "__main__":
    main()
