from app.services.pipeline import _attach_rubric_standards, _normalize_criteria_scores


def test_attaches_segment_rubric_standard_to_matching_criterion() -> None:
    envelope = {
        "criteria_scores": [
            {
                "name": "Architecture and Design",
                "score": 87.5,
                "level": "STRONG",
                "justification": "Clear logical divisions.",
                "confidence": 0.9,
            }
        ]
    }
    rubric = {
        "segments": [
            {
                "category": "Architecture and Design",
                "weight": "20%",
                "criteria": {
                    "4": "Strong organization with clear logical divisions.",
                    "5": "Excellent modularity and design patterns.",
                },
            }
        ]
    }

    _normalize_criteria_scores(envelope)
    _attach_rubric_standards(envelope, rubric)

    criterion = envelope["criteria_scores"][0]
    assert criterion["criterion_name"] == "Architecture and Design"
    assert criterion["rubric_standard"] == "Strong organization with clear logical divisions."
    assert criterion["rubric_weight"] == "20%"


def test_attaches_canonical_rubric_standard_to_matching_criterion() -> None:
    envelope = {
        "criteria_scores": [
            {
                "name": "Correctness",
                "score": 100,
                "level": "EXEMPLARY",
                "justification": "All tests pass.",
                "confidence": 0.95,
            }
        ]
    }
    rubric = {
        "criteria": [
            {
                "name": "Correctness",
                "max_points": 30,
                "levels": [
                    {"label": "EXEMPLARY", "points": 30, "description": "Fully correct."}
                ],
            }
        ]
    }

    _normalize_criteria_scores(envelope)
    _attach_rubric_standards(envelope, rubric)

    assert envelope["criteria_scores"][0]["rubric_standard"] == "Fully correct."


def test_human_review_level_does_not_attach_numeric_standard() -> None:
    envelope = {
        "criteria_scores": [
            {
                "name": "Testing and Validation",
                "score": 75,
                "level": "NEEDS_HUMAN_REVIEW",
                "justification": "Evidence is conflicting.",
                "confidence": 0.2,
            }
        ]
    }
    rubric = {
        "segments": [
            {
                "category": "Testing and Validation",
                "criteria": {"3": "Basic tests are present."},
            }
        ]
    }

    _normalize_criteria_scores(envelope)
    _attach_rubric_standards(envelope, rubric)

    assert "rubric_standard" not in envelope["criteria_scores"][0]
