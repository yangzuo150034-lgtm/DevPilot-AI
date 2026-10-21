import difflib

from app.core.security import allowed_path, digest, safe_path
from app.schemas import Proposal


def validate_patch(files: dict[str, str], proposal: dict, commit: str) -> dict:
    parsed = Proposal.model_validate(proposal)
    if not parsed.edits:
        raise ValueError("Agent did not propose a patch")
    candidate = dict(files)
    seen = set()
    for edit in parsed.edits:
        safe_path(edit.path)
        if not allowed_path(edit.path) or edit.path not in files:
            raise ValueError("Edits are limited to existing eligible source files")
        if edit.path in seen:
            raise ValueError("Combine edits to the same file into one replacement")
        if files[edit.path].count(edit.old) != 1:
            raise ValueError("Original text must match exactly once in the immutable snapshot")
        if edit.old == edit.new:
            raise ValueError("Patch must change the source")
        candidate[edit.path] = files[edit.path].replace(edit.old, edit.new, 1)
        if len(candidate[edit.path].encode()) > 50000:
            raise ValueError("Patched file exceeds size budget")
        seen.add(edit.path)
    diff = "".join(
        "".join(
            difflib.unified_diff(
                files[path].splitlines(keepends=True),
                candidate[path].splitlines(keepends=True),
                fromfile="a/" + path,
                tofile="b/" + path,
            )
        )
        for path in sorted(seen)
    )
    payload = {"commit": commit, "proposal": parsed.model_dump(), "diff": diff}
    return {**payload, "digest": digest(payload), "changed_paths": sorted(seen)}


def apply_patch(files: dict[str, str], patch: dict, commit: str) -> dict[str, str]:
    verified = validate_patch(files, patch["proposal"], commit)
    if verified["digest"] != patch["digest"]:
        raise ValueError("Patch or repository revision changed since review")
    result = dict(files)
    for edit in patch["proposal"]["edits"]:
        result[edit["path"]] = result[edit["path"]].replace(edit["old"], edit["new"], 1)
    return result
