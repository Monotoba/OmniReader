from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import piper_voices_dir
from ..persistence.settings_repo import SettingsRepository
from ..tts.cache import AudioCache


class SettingsDialog(QDialog):
    def __init__(
        self, settings: SettingsRepository, cache: AudioCache, parent=None
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.cache = cache
        self.setWindowTitle("OmniReader Settings")
        self.resize(600, 430)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.fields: dict[str, object] = {}
        tabs.addTab(self._tts_tab(), "TTS")
        tabs.addTab(self._filters_tab(), "Filters")
        tabs.addTab(self._reading_tab(), "Reading")
        tabs.addTab(self._storage_tab(), "Storage")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _page(self) -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        return page, QFormLayout(page)

    def _tts_tab(self) -> QWidget:
        page, form = self._page()
        backend = QComboBox()
        backend.addItems(["edge", "piper"])
        backend.setCurrentText(self.settings.get("tts.backend"))
        self.fields["tts.backend"] = backend
        form.addRow("Default backend", backend)
        for key, label in (
            ("tts.voice.edge", "Edge voice"),
            ("tts.voice.piper", "Piper voice/model"),
        ):
            field = QLineEdit(str(self.settings.get(key, "")))
            self.fields[key] = field
            form.addRow(label, field)
        for key, label, minimum, maximum in (
            ("tts.rate", "Rate", 0.5, 2.0),
            ("tts.pitch", "Pitch", -1.0, 1.0),
        ):
            field = QDoubleSpinBox()
            field.setRange(minimum, maximum)
            field.setSingleStep(0.1)
            field.setValue(float(self.settings.get(key)))
            self.fields[key] = field
            form.addRow(label, field)
        depth = QSpinBox()
        depth.setRange(0, 8)
        depth.setValue(int(self.settings.get("tts.buffer_depth")))
        self.fields["tts.buffer_depth"] = depth
        form.addRow("Look-ahead chunks", depth)
        models = QLineEdit(
            str(self.settings.get("tts.piper_models_dir", str(piper_voices_dir())))
        )
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda: self._choose_directory(models))
        row = QHBoxLayout()
        row.addWidget(models)
        row.addWidget(browse)
        self.fields["tts.piper_models_dir"] = models
        form.addRow("Piper voices directory", row)
        alignment = QCheckBox("Enable optional forced alignment")
        alignment.setChecked(bool(self.settings.get("tts.forced_alignment")))
        self.fields["tts.forced_alignment"] = alignment
        form.addRow(alignment)
        return page

    def _filters_tab(self) -> QWidget:
        page, form = self._page()
        for key, label in (
            ("filters.skip_headers_footers", "Skip headers and footers"),
            ("filters.skip_hidden", "Skip hidden text"),
            ("filters.skip_likely_hidden", "Skip likely-hidden text"),
            ("filters.skip_code", "Skip code blocks"),
            ("filters.skip_captions", "Skip captions and footnotes"),
        ):
            field = QCheckBox()
            field.setChecked(bool(self.settings.get(key)))
            self.fields[key] = field
            form.addRow(label, field)
        return page

    def _reading_tab(self) -> QWidget:
        page, form = self._page()
        for key, label in (
            ("reading.reopen_tabs", "Reopen tabs on startup"),
            ("reading.auto_scroll", "Auto-scroll during playback"),
        ):
            field = QCheckBox()
            field.setChecked(bool(self.settings.get(key)))
            self.fields[key] = field
            form.addRow(label, field)
        font = QLineEdit(str(self.settings.get("reading.font_family")))
        self.fields["reading.font_family"] = font
        form.addRow("Font family", font)
        size = QSpinBox()
        size.setRange(8, 48)
        size.setValue(int(self.settings.get("reading.font_size")))
        self.fields["reading.font_size"] = size
        form.addRow("Font size", size)
        for key, label in (
            ("reading.word_color", "Word highlight"),
            ("reading.sentence_color", "Sentence highlight"),
        ):
            field = QLineEdit(str(self.settings.get(key)))
            button = QPushButton("Choose…")
            button.clicked.connect(
                lambda _checked=False, target=field: self._choose_color(target)
            )
            row = QHBoxLayout()
            row.addWidget(field)
            row.addWidget(button)
            self.fields[key] = field
            form.addRow(label, row)
        return page

    def _storage_tab(self) -> QWidget:
        page, form = self._page()
        maximum = QSpinBox()
        maximum.setRange(32, 8192)
        maximum.setSuffix(" MB")
        maximum.setValue(int(self.settings.get("storage.cache_max_mb")))
        self.fields["storage.cache_max_mb"] = maximum
        form.addRow("Maximum audio cache", maximum)
        clear = QPushButton("Clear synthesized audio cache")
        clear.clicked.connect(self.cache.clear)
        form.addRow(clear)
        return page

    def _choose_directory(self, target: QLineEdit) -> None:
        value = QFileDialog.getExistingDirectory(
            self, "Choose Piper voices directory", target.text()
        )
        if value:
            target.setText(value)

    def _choose_color(self, target: QLineEdit) -> None:
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            target.setText(color.name())

    def _save(self) -> None:
        for key, field in self.fields.items():
            if isinstance(field, QCheckBox):
                value = field.isChecked()
            elif isinstance(field, QSpinBox | QDoubleSpinBox):
                value = field.value()
            elif isinstance(field, QComboBox):
                value = field.currentText()
            else:
                value = field.text()
            self.settings.set(key, value)
        self.cache.max_bytes = (
            int(self.settings.get("storage.cache_max_mb")) * 1024 * 1024
        )
        self.cache.prune()
        self.accept()
