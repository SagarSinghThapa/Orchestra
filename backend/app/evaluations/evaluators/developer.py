import difflib
import hashlib
import os
from pathlib import Path
import tempfile
import time
from typing import Optional

from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.metrics.ast_safety import (
    evaluate_ast_syntax,
    evaluate_diff_applicability,
    verify_preview_zero_mutation,
    verify_scope_compliance,
)
from app.evaluations.schemas import EvaluationCaseResultResponse, GoldenCase


class DeveloperASTEvaluator(BaseEvaluator):
    """
    Evaluates developer code modifications using static AST parsing, pure-Python
    diff applicability, scope containment, preview zero-mutation, and optimistic hash checks.
    Operates strictly inside an isolated temporary directory fixture.
    """

    @staticmethod
    def _compute_workspace_hash(workspace_dir: Path) -> str:
        """
        Recursively hashes all files in workspace_dir to verify zero mutation.
        """
        hasher = hashlib.sha256()
        for root, _, files in sorted(os.walk(workspace_dir)):
            for f in sorted(files):
                file_path = Path(root) / f
                hasher.update(f.encode("utf-8"))
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()

    async def evaluate_case(self, case: GoldenCase, run_id: str = "") -> EvaluationCaseResultResponse:
        t0 = time.perf_counter()

        file_path_rel = str(case.input_data.get("file_path", "test.py"))
        base_content = str(case.input_data.get("base_content", ""))
        new_content = str(case.input_data.get("new_content", ""))
        target_files = list(case.input_data.get("target_files", []))
        expected_hashes = dict(case.input_data.get("expected_file_hashes", {}))
        mode = str(case.input_data.get("mode", "preview"))

        # Ground truth expectations
        expect_ast_valid = bool(case.ground_truth.get("expected_ast_valid", True))
        expect_diff_applicable = bool(case.ground_truth.get("expected_diff_applicable", True))
        expect_scope_compliant = bool(case.ground_truth.get("expected_scope_compliant", True))
        expect_hash_collision = bool(case.ground_truth.get("expect_hash_collision", False))
        expect_zero_mutation = bool(case.ground_truth.get("expect_zero_mutation", True))

        failure_reason: Optional[str] = None

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            target_file_path = temp_path / file_path_rel
            target_file_path.parent.mkdir(parents=True, exist_ok=True)
            target_file_path.write_text(base_content, encoding="utf-8")

            # 1. Capture baseline workspace hash
            pre_hash = self._compute_workspace_hash(temp_path)

            # 2. Check base content hash vs expected_file_hashes if provided
            actual_base_hash = hashlib.sha256(base_content.encode("utf-8")).hexdigest()
            hash_collision_detected = False
            if expected_hashes:
                expected_hash = expected_hashes.get(file_path_rel)
                if expected_hash and expected_hash != actual_base_hash:
                    hash_collision_detected = True

            # 3. Static AST syntax validation
            ast_score, ast_err = evaluate_ast_syntax(new_content)

            # 4. Generate diff and verify line-by-line applicability
            diff = "".join(
                difflib.unified_diff(
                    base_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{file_path_rel}",
                    tofile=f"b/{file_path_rel}",
                )
            )
            diff_score, diff_err = evaluate_diff_applicability(base_content, diff)

            # 5. Scope compliance verification
            allowed_targets = case.ground_truth.get("allowed_targets", target_files)
            scope_score, scope_err = verify_scope_compliance([file_path_rel], allowed_targets)

            # 6. Verify preview mode does not mutate workspace
            post_hash = self._compute_workspace_hash(temp_path)
            mutation_score, mutation_err = verify_preview_zero_mutation(pre_hash, post_hash)

            # Assess criteria against ground truth
            ast_matched = (ast_score == 1.0) == expect_ast_valid
            diff_matched = (diff_score == 1.0) == expect_diff_applicable
            scope_matched = (scope_score == 1.0) == expect_scope_compliant
            hash_matched = hash_collision_detected == expect_hash_collision
            mutation_matched = (mutation_score == 1.0) == expect_zero_mutation

            passed = (
                ast_matched
                and diff_matched
                and scope_matched
                and hash_matched
                and mutation_matched
            )

            if not passed:
                if not ast_matched:
                    failure_reason = f"AST validity mismatch: expected {expect_ast_valid}, got {ast_score == 1.0} ({ast_err})"
                elif not diff_matched:
                    failure_reason = f"Diff applicability mismatch: expected {expect_diff_applicable}, got {diff_score == 1.0} ({diff_err})"
                elif not scope_matched:
                    failure_reason = f"Scope compliance mismatch: expected {expect_scope_compliant}, got {scope_score == 1.0} ({scope_err})"
                elif not hash_matched:
                    failure_reason = f"Hash collision mismatch: expected {expect_hash_collision}, got {hash_collision_detected}"
                elif not mutation_matched:
                    failure_reason = f"Preview mutation mismatch: expected zero mutation, but workspace changed"

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return EvaluationCaseResultResponse(
            id=0,
            run_id=run_id,
            case_id=case.case_id,
            status="passed" if passed else "failed",
            duration_ms=duration_ms,
            metrics={
                "ast_syntax_validity": ast_score,
                "patch_applicability": diff_score,
                "diff_scope_compliance": scope_score,
                "preview_zero_mutation": mutation_score,
            },
            failure_reason=failure_reason,
            details={
                "ast_error": ast_err,
                "diff_error": diff_err,
                "hash_collision": hash_collision_detected,
                "workspace_preserved": bool(mutation_score == 1.0),
            },
        )
