from src.bot.agent import MAX_REVISIONS, critic_router
from src.bot.prompts import build_drafter_prompt


def test_approved_draft_routes_to_splitter():
    assert (
        critic_router({"evaluation": {"approved": True}, "revision_count": 1})
        == "splitter"
    )


def test_rejected_draft_routes_to_drafter_before_limit():
    assert (
        critic_router({"evaluation": {"approved": False}, "revision_count": 1})
        == "drafter"
    )


def test_rejected_draft_stops_revising_at_limit():
    assert (
        critic_router(
            {"evaluation": {"approved": False}, "revision_count": MAX_REVISIONS}
        )
        == "splitter"
    )


def test_prompt_contains_memory_and_forbidden_terms():
    prompt = build_drafter_prompt(
        {
            "agent_name": "Nina",
            "role": "consultora",
            "objective": "orientar a compra",
            "voice": "direta",
            "formality": "media",
            "concision": "curta",
            "emoji_mode": "nunca",
            "commercial_initiative": 40,
            "max_questions": 1,
            "preferred_terms": ["claro"],
            "forbidden_terms": ["Como posso ajudar?"],
            "business_rules": "Nunca invente preço.",
        },
        {"target_chars": 180, "formality": "medium", "mirror_emojis": False},
        [{"key": "budget", "value": "5 mil"}],
    )

    assert "5 mil" in prompt
    assert "Como posso ajudar?" in prompt
    assert "no máximo 1 pergunta" in prompt
