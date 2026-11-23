import http.server
import json
import logging
import re
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class MockAIHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            body = {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if "/embeddings" in self.path:
            inputs = body.get("input", [])
            if isinstance(inputs, str):
                inputs = [inputs]
            data = [
                {
                    "object": "embedding",
                    "embedding": [0.01 * ((i % 10) + 1)] * 1536,
                    "index": i,
                }
                for i, _ in enumerate(inputs)
            ]
            response = {
                "object": "list",
                "data": data,
                "model": body.get("model", "text-embedding-3-small"),
                "usage": {"prompt_tokens": 10, "total_tokens": 10},
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            # Chat completions: determine intended schema based on messages
            messages = body.get("messages", [])
            all_text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))

            if "DraftResearchAnswer" in all_text or "draft" in all_text.lower() or "claims" in all_text.lower():
                evidence_ids = re.findall(r'id="(evidence_\d+)"', all_text)
                if not evidence_ids:
                    evidence_ids = ["evidence_1"]
                payload = {
                    "claims": [
                        {
                            "claim_text": "The platform architecture implements multi-agent coordination.",
                            "supporting_evidence_ids": [evidence_ids[0]],
                        }
                    ],
                    "summary_notes": "Smoke test research synthesis completed with grounded citations.",
                    "has_sufficient_evidence": True,
                }
            elif "ResearchPlan" in all_text or "subqueries" in all_text.lower():
                payload = {
                    "goal": "Deployment smoke test research investigation",
                    "subqueries": ["Orchestra architecture", "deployment verification"],
                    "strategy_notes": "Decomposed into conceptual inquiry.",
                }
            else:
                payload = {
                    "status": "success",
                    "summary": "Deployment smoke test developer task completed successfully.",
                    "patches": [],
                }

            response = {
                "id": "chatcmpl-mock-smoke-test",
                "object": "chat.completion",
                "created": 1700000000,
                "model": body.get("model", "gpt-4o-mini"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(payload),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = http.server.HTTPServer(("0.0.0.0", port), MockAIHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
