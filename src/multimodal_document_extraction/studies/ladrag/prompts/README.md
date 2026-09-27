# LAD-RAG prompts (verbatim transcription)

Source: Sourati et al., *LAD-RAG*, ACL 2026, Appendix H.2, Figures 9–12
(`papers/ladrag/2026.acl-long.724.pdf`, PDF pages 21–24). Transcribed in CP-4.1 with
`python scripts/transcribe_ladrag_prompts.py <this dir> 110`.

| File | Figure | Role | sha256 |
|---|---|---|---|
| `fig09_node_extraction.txt` | 9 | per-page element (node) extraction, with page image | `dd7484aa…877f` |
| `fig10_running_memory.txt` | 10 | `section_queue` update from section-like objects | `2b799af7…a1b` |
| `fig11_graph_construction.txt` | 11 | memory update + cross-page relationships, with page image | `895f5fed…cf` |
| `fig12_retriever_agent.txt` | 12 | retriever agent instructions | `4af9a876…9259` |

## Transcription method and fidelity

- Text from PyMuPDF. LaTeX `listings` wraps long lines and prefixes continuations with `,→`;
  PyMuPDF emits those markers after the block. Lines ≥ 110 characters are treated as wrapped and
  re-joined with one space; per block, the number of re-joined lines must equal the number of markers
  (0 mismatches; identical output for thresholds 100–110).
- **Word-exact, not whitespace-exact:** original indentation and blank lines are not recoverable from
  the PDF. Typos and quirks are kept as printed (e.g. Fig. 12 numbering jumps from 5 to 7;
  "matching wrt to", "use it as much possible" are not corrected).

## Templates

The prompts are Python format sources as printed in the paper; they are **not** edited here.
Rendering rules (see `docs/studies/ladrag/IMPLEMENTATION_SPEC.md` §3):

- Figs. 9 and 12 use `str.format`-style positional `{}` and `{{ }}` escapes.
- Figs. 10 and 11 are f-string sources whose placeholders are Python expressions
  (e.g. `{json.dumps(working_memory, indent=2)}`) plus `{{ }}` escapes.
- Our renderer replaces each placeholder by exact string match and then unescapes `{{`→`{`,
  `}}`→`}` — i.e. the model sees what the paper's f-strings would have produced.
