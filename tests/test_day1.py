from research_compass.exploration import SearchBranch, build_branches, default_branch_keys
from research_compass.retrieval import paper_from_work, search_papers


def test_branches_use_the_interest_and_optional_context():
    branches = build_branches("  AI   robot control ", " manipulation ")
    assert len(branches) == 4
    assert branches[0].query == "AI robot control manipulation"
    assert default_branch_keys("challenges") == ["overview", "challenges"]


def test_paper_keeps_abstract_and_original_source():
    paper = paper_from_work(
        {
            "id": "https://openalex.org/W123",
            "title": "Real paper",
            "publication_year": 2024,
            "abstract": "Actual OpenAlex abstract.",
            "doi": "https://doi.org/10.1234/example",
            "primary_location": {"landing_page_url": "https://publisher.example/paper"},
        },
        "overview",
    )
    assert paper.abstract == "Actual OpenAlex abstract."
    assert paper.source_url == "https://publisher.example/paper"
    assert not paper.is_demo


def test_pyalex_style_work_reconstructs_abstract():
    class PyAlexStyleWork(dict):
        def __getitem__(self, key):
            if key == "abstract":
                return "Reconstructed abstract."
            return super().__getitem__(key)

    work = PyAlexStyleWork(id="https://openalex.org/W123", abstract_inverted_index={"Reconstructed": [0]})
    assert paper_from_work(work, "overview").abstract == "Reconstructed abstract."


def test_live_search_deduplicates_papers_and_tracks_queries():
    class FakeSearch:
        def search(self, query):
            return self

        def filter(self, **kwargs):
            assert kwargs == {"has_abstract": True}
            return self

        def get(self, per_page):
            return [{"id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/x", "title": "A"}]

    branches = [
        SearchBranch("overview", "Overview", "", "robot control"),
        SearchBranch("methods", "Methods", "", "robot control methods"),
    ]
    outcome = search_papers(branches, search_factory=FakeSearch)
    assert outcome.mode == "live"
    assert len(outcome.papers) == 1
    assert outcome.papers[0].found_by == ["overview", "methods"]
    assert len(outcome.queries) == 2
    assert outcome.queries[0].ranked_results[0]["raw_rank"] == 1
    assert outcome.queries[0].ranked_results[0]["status"] == "Retrieved"
    assert len(outcome.queries[0].raw_results) == 1


def test_cross_match_openalex_id_and_doi_merges_duplicate_records():
    class FakeSearch:
        call_index = 0

        def search(self, query):
            return self

        def filter(self, **kwargs):
            return self

        def get(self, per_page):
            work = works[type(self).call_index]
            type(self).call_index += 1
            return [work]

    from research_compass.exploration import SearchBranch
    from research_compass.retrieval import search_papers

    works = [
        {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/a", "title": "A"},
        {"id": "https://openalex.org/W2", "doi": "https://doi.org/10.1/b", "title": "B"},
        {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/b", "title": "A alias"},
    ]
    branches = [SearchBranch(f"b{i}", f"B{i}", "", "same query") for i in range(3)]
    outcome = search_papers(branches, search_factory=FakeSearch, per_branch=1)
    assert len(outcome.papers) == 1
    assert outcome.papers[0].id == "https://openalex.org/W1"
    assert outcome.papers[0].found_by == ["b0", "b1", "b2"]
    assert outcome.queries[2].ranked_results[0]["duplicate_of"] == "https://openalex.org/W1"


def test_api_failure_uses_explicit_demo_records():
    class RateLimitError(Exception):
        response = type("Response", (), {"status_code": 429})()

    class FailingSearch:
        def search(self, query):
            raise RateLimitError()

    branch = SearchBranch("overview", "Overview", "", "robot control")
    outcome = search_papers([branch], search_factory=FailingSearch)
    assert outcome.mode == "demo"
    assert all(paper.is_demo and paper.source_url is None for paper in outcome.papers)
    assert "429" in outcome.notice
