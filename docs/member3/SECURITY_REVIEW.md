# Member 3 Security Review

## Threat Model & Attack Surface
The Developer Subgraph introduces powerful capabilities to read, evaluate, and write code to the file system. The primary attack surfaces include:
- **Malicious Developer Input**: Exploiting MCP tools via prompt injection or crafted payloads to escape the sandbox or exfiltrate environment secrets.
- **Dependency/Repository Poisoning**: Analyzing a repository containing malicious configurations or prompt injection attempts designed to subvert agent reasoning or generate backdoored code.
- **Resource Exhaustion (Denial of Service)**: Submitting infinitely expanding directory structures or ReDoS patterns designed to crash the API process.

---

## Security Control Status

### 1. Filesystem Security
**Status:** PROTECTED
- Enforced strictly via `resolve_safe_path` within `MCPGateway`.
- Null-byte injection is blocked.
- Path traversal utilizing `../` or absolute path breakouts is actively rejected, raising `E1xx` validation errors.

### 2. Sandbox Security
**Status:** PROTECTED
- File access is strictly constrained to the user's `workspace_root`.
- Agents cannot access internal application state, `.env` files, or OS-level sensitive files outside the designated workspace.

### 3. Git/Subprocess Security
**Status:** PROTECTED
- Git operations (`git log`, `git diff`, `git status`) use safe subprocess invocation with parameterized lists instead of raw shell evaluation `shell=True`.
- This mitigates arbitrary shell injection risks from crafted file names or repository artifacts.

### 4. MCP Security
**Status:** PROTECTED
- JSON Schema validation is strictly applied to all tool arguments before tool execution.
- Malformed inputs are rejected cleanly without crashing the gateway.
- Timeout safety wrappers prevent indefinitely hanging tool executions.

### 5. Repository-Content / Prompt-Injection Security
**Status:** PARTIALLY PROTECTED
- Known, common prompt injection vectors (`[INST]`, `ignore previous instructions`) are actively scrubbed and filtered by the Documentation Agent.
- However, zero-day injection techniques or highly obfuscated jailbreaks might still bypass simple substring matching. LLM-layer evaluation is needed for robust verification.

### 6. Resource Exhaustion Protection
**Status:** PROTECTED
- Max file depth limits (e.g., `MAX_TREE_DEPTH = 6`).
- Max payload limits (e.g., 5MB JSON argument bounds).
- File read limits (1MB cap) and Regex backtracking (ReDoS) heuristic checks prevent CPU or memory starvation.

### 7. Secret Handling & Logging Security
**Status:** PROTECTED
- Internal logger utilizes a `scrub_secrets` regex function to mask detected API keys or JWT tokens before committing traces or stdout output.
- Passwords and keys are never sent in plaintext inside trace responses.

### 8. Frontend Security
**Status:** PROTECTED
- All inputs are properly sanitized via React/Next.js native XSS protections.
- API requests are wrapped in typed boundaries, preventing untrusted DOM manipulation.
- (Mock auth currently requires backend wiring).

---

## M1/M2 Integration Security Dependencies

### Evaluation Contracts
**Status:** BLOCKED BY M1
- The schemas defining how the Developer Subgraph's outputs will be safely ingested and evaluated by Member 1's benchmarking suite are not yet defined.

### Global Authentication & Error Routing
**Status:** BLOCKED BY M2
- The `/login` system currently utilizes a mock local storage strategy. It relies entirely on Member 2 to wire the production JWT architecture and shared E1xx-E5xx error taxonomy handling.

---

## Known Limitations
- The prompt injection filter uses basic matching. Evolving models will require semantic-level prompt defense filters.
- ReDoS protection uses a heuristic regex. It protects against obvious catastrophic backtracking but does not replace a comprehensive static analysis tool.
