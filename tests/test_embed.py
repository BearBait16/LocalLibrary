from types import SimpleNamespace

from locallibrary import embed


class FakeClient:
    def __init__(self):
        self.calls = []

    def embed(self, model, input):
        self.calls.append(list(input))
        return SimpleNamespace(embeddings=[[float(len(t))] for t in input])


def test_prefixes_and_batching(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(embed, "_client", lambda: fake)
    progress = []
    vectors = embed.embed_documents([f"t{i}" for i in range(70)], lambda done, total: progress.append((done, total)))
    assert len(vectors) == 70
    assert [len(c) for c in fake.calls] == [32, 32, 6]
    assert all(t.startswith("search_document: ") for c in fake.calls for t in c)
    assert progress[-1] == (70, 70)
    embed.embed_query("what is a mean?")
    assert fake.calls[-1] == ["search_query: what is a mean?"]
