#!/usr/bin/env python3
"""DRY (Don't Repeat Yourself) enforcement tool."""

import argparse
import ast
import difflib
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from tools.utils import Colors, get_project_root, print_colored, print_error, print_info


class CodeBlock:
    def __init__(self, file_path: Path, start_line: int, end_line: int, content: str):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.hash = hashlib.md5(  # nosec B324 - used for non-security fingerprinting
            content.encode(),
            usedforsecurity=False,
        ).hexdigest()

    def __repr__(self):
        return (
            f"{self.file_path}:{self.start_line}-{self.end_line} "
            f"({self.end_line - self.start_line + 1} lines)"
        )


class DuplicationDetector:
    def __init__(self, min_lines: int = 5, similarity_threshold: float = 0.8):
        self.min_lines = min_lines
        self.similarity_threshold = similarity_threshold
        self.blocks: list[CodeBlock] = []
        self.duplicates: list[tuple[CodeBlock, CodeBlock, float]] = []

    def extract_functions(self, file_path: Path) -> list[CodeBlock]:
        blocks = []
        try:
            with open(file_path) as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start_line = node.lineno
                    end_line = node.end_lineno or start_line
                    if end_line - start_line + 1 >= self.min_lines:
                        func_content = "\n".join(
                            content.splitlines()[start_line - 1 : end_line]
                        )
                        blocks.append(
                            CodeBlock(file_path, start_line, end_line, func_content)
                        )
        except SyntaxError:
            print_error(f"Syntax error in {file_path}, skipping")
        except Exception as exc:
            print_error(f"Error processing {file_path}: {exc}")
        return blocks

    def extract_code_blocks(self, file_path: Path) -> list[CodeBlock]:
        blocks: list[CodeBlock] = []
        try:
            with open(file_path) as f:
                lines = f.readlines()

            if len(lines) < self.min_lines:
                return blocks

            for i in range(len(lines) - self.min_lines + 1):
                for window_size in range(self.min_lines, min(50, len(lines) - i + 1)):
                    content = "".join(lines[i : i + window_size])
                    stripped = content.strip()
                    if len(stripped) < 20:
                        continue
                    if stripped.count("#") / len(stripped.splitlines()) > 0.5:
                        continue
                    blocks.append(
                        CodeBlock(file_path, i + 1, i + window_size, content.strip())
                    )
        except Exception as exc:
            print_error(f"Error reading {file_path}: {exc}")
        return blocks

    def calculate_similarity(self, block1: CodeBlock, block2: CodeBlock) -> float:
        content1 = " ".join(block1.content.split())
        content2 = " ".join(block2.content.split())
        matcher = difflib.SequenceMatcher(None, content1, content2)
        return matcher.ratio()

    def find_duplicates(  # noqa: C901 - duplication detection is intentionally verbose
        self, files: list[Path], use_functions: bool = False
    ):
        print_info(f"Analyzing {len(files)} Python files...")

        for file_path in files:
            if use_functions:
                blocks = self.extract_functions(file_path)
            else:
                blocks = self.extract_code_blocks(file_path)
            self.blocks.extend(blocks)

        print_info(f"Found {len(self.blocks)} code blocks to analyze")

        hash_groups: dict[str, list[CodeBlock]] = defaultdict(list)
        for block in self.blocks:
            hash_groups[block.hash].append(block)

        for blocks in hash_groups.values():
            if len(blocks) > 1:
                for i in range(len(blocks)):
                    for j in range(i + 1, len(blocks)):
                        self.duplicates.append((blocks[i], blocks[j], 1.0))

        seen_pairs: set[tuple[str, str]] = set()
        for i, block1 in enumerate(self.blocks):
            if i % 100 == 0 and i > 0:
                print_info(f"Progress: {i}/{len(self.blocks)} blocks analyzed")
            for block2 in self.blocks[i + 1 :]:
                if block1.file_path == block2.file_path and not (
                    block1.end_line < block2.start_line
                    or block2.end_line < block1.start_line
                ):
                    continue
                pair_key = (
                    f"{block1.file_path}:{block1.start_line}",
                    f"{block2.file_path}:{block2.start_line}",
                )
                if pair_key in seen_pairs:
                    continue
                similarity = self.calculate_similarity(block1, block2)
                if similarity >= self.similarity_threshold and similarity < 1.0:
                    self.duplicates.append((block1, block2, similarity))
                    seen_pairs.add(pair_key)

    def print_report(self):
        if not self.duplicates:
            print_colored("\n✓ No significant code duplication found!", Colors.GREEN)
            return

        print_colored(
            f"\n✗ Found {len(self.duplicates)} duplicate code blocks",
            Colors.RED,
        )
        sorted_dupes = sorted(self.duplicates, key=lambda x: x[2], reverse=True)

        print("\n" + "=" * 80)
        print("DUPLICATION REPORT")
        print("=" * 80)

        for idx, (block1, block2, similarity) in enumerate(sorted_dupes, 1):
            print(f"\n{idx}. Similarity: {similarity:.1%}")
            print(f"   Location 1: {block1}")
            print(f"   Location 2: {block2}")
            if similarity == 1.0:
                print(f"   {Colors.RED}EXACT DUPLICATE{Colors.NC}")
            else:
                print(f"   {Colors.YELLOW}SIMILAR CODE ({similarity:.1%}){Colors.NC}")

        print("\n" + "=" * 80)
        print("REMEDIATION TASKS")
        print("=" * 80)

        file_groups: dict[Path, list[tuple]] = defaultdict(list)
        for block1, block2, similarity in sorted_dupes:
            file_groups[block1.file_path].append((block1, block2, similarity))

        for file_path, duplicates in file_groups.items():
            print(f"\n{Colors.CYAN}{file_path}{Colors.NC}")
            for block1, block2, similarity in duplicates:
                if similarity == 1.0:
                    print(
                        f"  [ ] Extract duplicate code at lines "
                        f"{block1.start_line}-{block1.end_line} to shared function"
                    )
                    print(f"      Also found in: {block2.file_path}")
                else:
                    print(
                        f"  [ ] Review similar code at lines "
                        f"{block1.start_line}-{block1.end_line}"
                    )
                    print(
                        f"      Similar to: {block2.file_path}:"
                        f"{block2.start_line}-{block2.end_line}"
                    )


def find_python_files(root: Path, exclude_dirs: set[str] | None = None) -> list[Path]:
    if exclude_dirs is None:
        exclude_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
        }

    python_files = []
    for path in root.rglob("*.py"):
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue
        python_files.append(path)
    return python_files


def main():
    parser = argparse.ArgumentParser(
        description="Detect code duplication in Python files"
    )
    parser.add_argument(
        "--min-lines", type=int, default=5, help="Minimum lines per block"
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.8,
        help="Similarity threshold 0-1 (default: 0.8)",
    )
    parser.add_argument(
        "--functions-only",
        action="store_true",
        help="Only analyze function definitions",
    )
    parser.add_argument(
        "--path", type=str, help="Path to analyze (default: project root)"
    )

    args = parser.parse_args()

    root = Path(args.path).resolve() if args.path else get_project_root()

    print_colored("DRY (Don't Repeat Yourself) Enforcement Tool", Colors.CYAN)
    print_colored("=" * 50, Colors.CYAN)
    print(f"Analyzing: {root}")
    print(f"Min lines: {args.min_lines}")
    print(f"Similarity threshold: {args.similarity:.0%}")
    print(f"Mode: {'Functions only' if args.functions_only else 'All code blocks'}\n")

    files = find_python_files(root)
    if not files:
        print_error("No Python files found!")
        sys.exit(1)

    detector = DuplicationDetector(
        min_lines=args.min_lines, similarity_threshold=args.similarity
    )
    detector.find_duplicates(files, use_functions=args.functions_only)
    detector.print_report()

    if detector.duplicates:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
