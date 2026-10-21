from pathlib import PurePosixPath

from tree_sitter import Language, Parser

from app.core.security import digest


def parser_for(path: str):
    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        import tree_sitter_python as grammar

        language = grammar.language()
    elif suffix in {".js", ".jsx"}:
        import tree_sitter_javascript as grammar

        language = grammar.language()
    elif suffix in {".ts", ".tsx"}:
        import tree_sitter_typescript as grammar

        language = grammar.language_tsx() if suffix == ".tsx" else grammar.language_typescript()
    else:
        return None
    return Parser(Language(language))


def chunk_files(files: dict[str, str], commit: str) -> list[dict]:
    chunks = []
    for path, content in sorted(files.items()):
        lines = content.splitlines()
        parser = parser_for(path)
        boundaries = {0, len(lines)}
        parsed = False
        if parser:
            tree = parser.parse(content.encode("utf-8"))
            if not tree.root_node.has_error:
                parsed = True
                for node in tree.root_node.named_children:
                    boundaries.add(node.start_point.row)
                    boundaries.add(min(node.end_point.row + 1, len(lines)))
        positions = sorted(boundaries)
        for start, end in zip(positions, positions[1:], strict=False):
            for offset in range(start, end, 60):
                stop = min(offset + 60, end)
                text = "\n".join(lines[offset:stop])
                if not text.strip():
                    continue
                chunks.append(
                    {
                        "id": digest([commit, path, offset, stop]),
                        "path": path,
                        "start_line": offset + 1,
                        "end_line": stop,
                        "text": text,
                        "parser": "tree-sitter" if parsed else "line-fallback",
                        "commit": commit,
                    }
                )
    return chunks
