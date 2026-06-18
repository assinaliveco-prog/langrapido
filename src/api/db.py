from src.api.repository import get_repository


def get_personality():
    settings = get_repository().get_settings()
    return {
        "system_prompt": settings["business_rules"]
        or (
            f"Você é {settings['agent_name']}, {settings['role']}. "
            f"Seu objetivo é {settings['objective']}. "
            f"Sua voz é {settings['voice']}."
        ),
        "slang_level": settings["formality"],
        "use_emojis": settings["emoji_mode"] != "nunca",
    }


def update_personality(prompt: str, slang_level: str, use_emojis: bool):
    mapping = {"baixo": "alta", "medio": "media", "alto": "baixa"}
    return get_repository().update_settings(
        {
            "business_rules": prompt,
            "formality": mapping.get(slang_level, slang_level),
            "emoji_mode": "espelhar" if use_emojis else "nunca",
        }
    )
