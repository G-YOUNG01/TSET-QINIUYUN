from src.layout import LayoutEngine
from src.models import PanelPrompt


def test_layout_assigns_frames():
    engine = LayoutEngine()
    prompts = [
        PanelPrompt(chapter_index=1, scene_index=1, panel_index=i, description="panel")
        for i in range(1, 3)
    ]
    placements = engine.assign_layouts(prompts)
    assert len(placements) == 2
    for key in placements:
        assert key[0] == 1
        assert key[1] == 1