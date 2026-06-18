from src.services.humanization import (
    infer_style,
    safe_typo,
    split_semantically,
    timing_for,
)


def test_short_urgent_message_produces_short_direct_style():
    style = infer_style("preço? preciso disso hj")
    assert style.target_chars <= 180
    assert style.urgency == "high"
    assert style.max_questions == 1


def test_formal_language_is_detected_without_forcing_slang():
    style = infer_style("Boa tarde. Poderia me enviar as condições, por favor?")
    assert style.formality == "high"


def test_short_message_is_not_split():
    assert split_semantically("sim, consigo te enviar ainda hoje") == [
        "sim, consigo te enviar ainda hoje"
    ]


def test_long_message_is_split_at_semantic_boundaries():
    text = (
        "entendi o que você precisa e consigo te orientar sem enrolação. "
        "primeiro eu comparo as duas opções que cabem no seu cenário. "
        "depois, se fizer sentido, te mando os valores certinhos e o prazo."
    )
    chunks = split_semantically(text, max_chunks=3, target_chars=90)
    assert 2 <= len(chunks) <= 3
    assert " ".join(chunks) == text


def test_sensitive_tokens_never_receive_typo():
    text = "Ana, o valor é R$ 2.490 e meu número é 11999998888"
    for seed in range(30):
        changed = safe_typo(text, probability=0.05, seed=seed)
        assert "Ana" in changed
        assert "R$ 2.490" in changed
        assert "11999998888" in changed


def test_timing_is_bounded():
    timing = timing_for("consigo te mostrar duas opções")
    assert 0.4 <= timing.thinking_seconds <= 2.5
    assert 0.8 <= timing.typing_seconds <= 8
