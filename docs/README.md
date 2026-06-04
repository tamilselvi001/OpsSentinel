# docs/ — source specifications

Place the two source documents here so Claude Code can reference them when a phase
wants more depth. They are git-ignored (see root `.gitignore`) and stay local only.

| File | What it is |
|------|------------|
| `architecture-spec.pdf` | OpsSentinel Master Architecture & MVP Specification |
| `project-document.pdf`  | OpsSentinel project document / requirements |

> The phase prompts in [`../PROMPTS/`](../PROMPTS) are self-contained — every contract
> Claude Code needs is restated inline, so the build is correct even if these PDFs are
> absent. The PDFs add depth, not correctness.

Phase 1 may also reference `docs/mvp.pdf` (Phase-1 prompt, §How to use). If you only have
one combined spec, you can copy/symlink it to that name as well.
