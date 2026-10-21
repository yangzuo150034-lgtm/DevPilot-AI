import httpx

from app.rag.chunks import chunk_files
from app.repositories import DEMO_FILES, import_github


def test_chunk_citations_match_exact_source():
    for chunk in chunk_files(DEMO_FILES, "commit-123"):
        lines = DEMO_FILES[chunk["path"]].splitlines()
        assert chunk["text"] == "\n".join(lines[chunk["start_line"] - 1 : chunk["end_line"]])
        assert chunk["commit"] == "commit-123"
    assert any(c["parser"] == "tree-sitter" for c in chunk_files(DEMO_FILES, "x"))


def test_three_retrieval_modes(service):
    repo = service.import_repository("demo://calculator")
    for mode in ["keyword", "vector", "hybrid"]:
        results = service.retrieve(repo["id"], "def add sum return", mode)
        assert results
        assert any(c["path"] == "calculator.py" and "def add" in c["text"] for c in results)
        assert all(c["embedding"] == "hash" for c in results)


def test_github_import_pins_commit_and_excludes_symlink_and_secret(settings):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        if request.url.path.endswith("/commits/HEAD"):
            return httpx.Response(200, json={"sha": "a" * 40})
        if "/git/trees/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {
                            "type": "blob",
                            "path": "app.py",
                            "mode": "100644",
                            "size": 4,
                            "sha": "blob-a",
                        },
                        {
                            "type": "blob",
                            "path": ".env",
                            "mode": "100644",
                            "size": 4,
                            "sha": "secret",
                        },
                        {
                            "type": "blob",
                            "path": "link.py",
                            "mode": "120000",
                            "size": 4,
                            "sha": "link",
                        },
                    ]
                },
            )
        assert request.url.path.endswith("/git/blobs/blob-a")
        return httpx.Response(200, json={"encoding": "base64", "content": "eD0xCg=="})

    repo = import_github(
        "https://github.com/example/repository", settings, httpx.MockTransport(handler)
    )
    assert repo["files"] == {"app.py": "x=1\n"}
    assert any("a" * 40 in url for url in requested)
    assert not any(url.endswith("/secret") or url.endswith("/link") for url in requested)
