from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGroupBox, QVBoxLayout

from ..document.filters import FilterSettings


class FilterPanel(QGroupBox):
    filters_changed = Signal(object)

    _OPTIONS = (
        ("skip_headers_footers", "Skip headers and footers"),
        ("skip_hidden", "Skip hidden text"),
        ("skip_likely_hidden", "Skip likely-hidden text"),
        ("skip_code", "Skip code blocks"),
        ("skip_captions", "Skip captions and footnotes"),
    )

    def __init__(self, settings: FilterSettings, parent=None) -> None:
        super().__init__("Reading filters", parent)
        self.setCheckable(True)
        self.setChecked(False)
        layout = QVBoxLayout(self)
        self.checkboxes: dict[str, QCheckBox] = {}
        for name, label in self._OPTIONS:
            checkbox = QCheckBox(label)
            checkbox.setChecked(getattr(settings, name))
            checkbox.toggled.connect(self._emit)
            self.checkboxes[name] = checkbox
            layout.addWidget(checkbox)

    def value(self) -> FilterSettings:
        return FilterSettings(
            **{name: checkbox.isChecked() for name, checkbox in self.checkboxes.items()}
        )

    def _emit(self, _checked: bool) -> None:
        self.filters_changed.emit(self.value())
