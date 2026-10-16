"""Right-click → Change look…: pick a shelf book's spine color and edge design."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout

from locallibrary.looks import DESIGN_NAMES, SPINE_COLORS, SPINE_DESIGNS
from locallibrary.ui.widgets import BookSpine


class SpineLookDialog(QDialog):
    def __init__(self, title: str, color: int, design: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SpineLookDialog")
        self.setWindowTitle("Change look")
        self.color, self.design = color, design
        layout = QHBoxLayout(self)

        self.preview = BookSpine(0, title, color, design)
        layout.addWidget(self.preview)

        choices = QVBoxLayout()
        layout.addLayout(choices)
        heading = QLabel("Color")
        heading.setObjectName("ColumnHeading")
        choices.addWidget(heading)
        color_row = QHBoxLayout()
        self.color_spines = []
        for index, name in enumerate(SPINE_COLORS):
            spine = BookSpine(index, name, index, design)
            spine.clicked.connect(self.choose_color)
            color_row.addWidget(spine)
            self.color_spines.append(spine)
        choices.addLayout(color_row)

        heading = QLabel("Edge design")
        heading.setObjectName("ColumnHeading")
        choices.addWidget(heading)
        design_row = QHBoxLayout()
        self.design_spines = []
        for index, key in enumerate(SPINE_DESIGNS):
            spine = BookSpine(index, DESIGN_NAMES[key], color, key)
            spine.clicked.connect(lambda i: self.choose_design(SPINE_DESIGNS[i]))
            design_row.addWidget(spine)
            self.design_spines.append(spine)
        design_row.addStretch()
        choices.addLayout(design_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        choices.addWidget(buttons)
        self._refresh()

    def choose_color(self, index: int) -> None:
        self.color = index
        self._refresh()

    def choose_design(self, design: str) -> None:
        self.design = design
        self._refresh()

    def _refresh(self) -> None:
        self.preview.set_look(self.color, self.design)
        for spine in self.color_spines:  # color samples show the chosen design, and vice versa
            spine.set_look(spine.item_id, self.design)
            self._select(spine, spine.item_id == self.color)
        for spine in self.design_spines:
            key = SPINE_DESIGNS[spine.item_id]
            spine.set_look(self.color, key)
            self._select(spine, key == self.design)

    @staticmethod
    def _select(spine: BookSpine, selected: bool) -> None:
        spine.setProperty("selected", selected)
        spine.style().unpolish(spine)
        spine.style().polish(spine)
