from src.models import PanelPrompt


def test_panel_prompt_defaults():
    prompt = PanelPrompt(
        chapter_index=1,
        scene_index=1,
        panel_index=1,
        description="A test panel",
    )
    assert prompt.dialogue == []
    assert prompt.style == ""
