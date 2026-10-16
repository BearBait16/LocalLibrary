"""Spine looks for shelf books: palette names and designs. The actual colors live in ui/style.qss."""
from collections import Counter

# Index i matches QFrame#ShelfSpine[spineColor="i"] in style.qss.
SPINE_COLORS = ["Oxblood", "Navy", "Forest", "Mustard", "Plum", "Teal", "Chocolate", "Slate"]
SPINE_DESIGNS = ["bands", "label", "two_tone", "ribbed"]
DESIGN_NAMES = {"bands": "Gold bands", "label": "Title label", "two_tone": "Two-tone", "ribbed": "Ribbed spine"}


def _least_used(options: list, used: Counter, avoid) -> object:
    candidates = [o for o in options if o != avoid] or options
    return min(candidates, key=lambda o: (used[o], options.index(o)))


def pick_look(existing: list[tuple[int, str]], neighbor: tuple[int, str] | None = None) -> tuple[int, str]:
    """Least-used color and design across `existing` looks, never matching the neighbor's color or design."""
    colors = Counter(c for c, _ in existing)
    designs = Counter(d for _, d in existing)
    avoid_color, avoid_design = neighbor if neighbor else (None, None)
    color = _least_used(list(range(len(SPINE_COLORS))), colors, avoid_color)
    design = _least_used(SPINE_DESIGNS, designs, avoid_design)
    return color, design
