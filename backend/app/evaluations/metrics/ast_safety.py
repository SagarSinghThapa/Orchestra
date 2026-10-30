import ast
import difflib
import re
from typing import List, Optional, Tuple


def evaluate_ast_syntax(code: str) -> Tuple[float, Optional[str]]:
    """
    Validates Python code syntax using Python's standard ast.parse().
    Emits (1.0, None) on clean parse; (0.0, error_message) on SyntaxError.
    """
    try:
        ast.parse(code)
        return 1.0, None
    except SyntaxError as e:
        return 0.0, f"SyntaxError: {e.msg} at line {e.lineno}"
    except Exception as e:
        return 0.0, f"ParseError: {str(e)}"


def evaluate_diff_applicability(base_text: str, diff_text: str) -> Tuple[float, Optional[str]]:
    """
    Deterministically applies a unified diff to base_text in pure Python without subprocesses.
    Reconstructs the target text line by line and verifies context line integrity.
    """
    if not diff_text.strip():
        return 1.0, None

    base_lines = base_text.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)

    # Parse hunk headers: @@ -start,count +start,count @@
    hunk_header_pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    output_lines: List[str] = []
    base_idx = 0
    in_hunks = False

    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]

        # Skip diff headers
        if line.startswith("---") or line.startswith("+++"):
            i += 1
            continue

        match = hunk_header_pattern.match(line)
        if match:
            in_hunks = True
            hunk_start = int(match.group(1)) - 1  # 0-indexed
            # Copy untouched lines prior to this hunk
            while base_idx < hunk_start and base_idx < len(base_lines):
                output_lines.append(base_lines[base_idx])
                base_idx += 1

            i += 1
            while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                hline = diff_lines[i]
                if hline.startswith("---") or hline.startswith("+++"):
                    i += 1
                    continue
                tag = hline[0] if hline else ""
                content = hline[1:]

                if tag == " ":
                    # Context line: must match base line
                    if base_idx >= len(base_lines):
                        return 0.0, f"Hunk context overflow at line {base_idx + 1}"
                    if base_lines[base_idx] != content:
                        return (
                            0.0,
                            f"Hunk context mismatch at line {base_idx + 1}: expected '{base_lines[base_idx].strip()}', got '{content.strip()}'",
                        )
                    output_lines.append(base_lines[base_idx])
                    base_idx += 1
                elif tag == "-":
                    # Deleted line: must match base line
                    if base_idx >= len(base_lines):
                        return 0.0, f"Hunk deletion overflow at line {base_idx + 1}"
                    if base_lines[base_idx] != content:
                        return (
                            0.0,
                            f"Hunk deletion mismatch at line {base_idx + 1}: expected '{base_lines[base_idx].strip()}', got '{content.strip()}'",
                        )
                    base_idx += 1
                elif tag == "+":
                    # Added line
                    output_lines.append(content)
                elif tag == "\\":
                    # "\ No newline at end of file"
                    pass
                else:
                    pass
                i += 1
            continue

        i += 1

    if not in_hunks:
        return 1.0, None

    # Copy remaining untouched base lines
    while base_idx < len(base_lines):
        output_lines.append(base_lines[base_idx])
        base_idx += 1

    return 1.0, None


def verify_scope_compliance(modified_paths: List[str], allowed_targets: List[str]) -> Tuple[float, Optional[str]]:
    """
    Verifies that modified paths are strictly within allowed target paths and count <= 5.
    """
    if not modified_paths:
        return 1.0, None

    if not allowed_targets:
        return 0.0, "Allowed targets list is empty; modifications rejected"

    mod_set = set(modified_paths)
    allowed_set = set(allowed_targets)

    if len(mod_set) > 5:
        return 0.0, f"Modified files count ({len(mod_set)}) exceeds maximum limit of 5"

    unauthorized = mod_set - allowed_set
    if unauthorized:
        return 0.0, f"Modified files {sorted(unauthorized)} exceed allowed targets {sorted(allowed_set)}"

    return 1.0, None


def verify_preview_zero_mutation(pre_hash: str, post_hash: str) -> Tuple[float, Optional[str]]:
    """
    Verifies that the workspace hash before preview is identical to the hash after preview.
    """
    if pre_hash == post_hash:
        return 1.0, None
    return 0.0, f"Preview mode caused workspace mutation ({pre_hash[:8]} -> {post_hash[:8]})"
