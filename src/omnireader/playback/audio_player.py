from __future__ import annotations

import os
import shutil
import signal
import sys
import time
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class AudioPlayer(QObject):
    """Play synthesized audio out-of-process to isolate native backend faults.

    Some Qt/PipeWire combinations abort or segfault when PipeWire is installed
    but unavailable. ffplay/mpv failures are contained in a child process and
    reported through ``error`` instead of terminating OmniReader.
    """

    position_changed = Signal(int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        found = self._find_player()
        self._program = found[0] if found else None
        self._base_arguments = found[1] if found else []
        self._process = QProcess(self)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        environment = QProcessEnvironment.systemEnvironment()
        if (
            sys.platform.startswith("linux")
            and self._program is not None
            and self._program.name == "ffplay"
        ):
            # SDL's PulseAudio driver works with both PulseAudio and the
            # pipewire-pulse compatibility service and avoids Qt's crashing
            # PipeWire integration.
            environment.insert("SDL_AUDIODRIVER", "pulseaudio")
        self._process.setProcessEnvironment(environment)
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._emit_position)
        self._elapsed_ms = 0
        self._started_at: float | None = None
        self._stopping = False

    @staticmethod
    def _find_player() -> tuple[Path, list[str]] | None:
        ffplay = shutil.which("ffplay")
        if ffplay:
            return Path(ffplay), [
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "error",
                "-nostats",
            ]
        mpv = shutil.which("mpv")
        if mpv:
            return Path(mpv), ["--no-video", "--really-quiet", "--audio-display=no"]
        return None

    def play(self, path: Path) -> None:
        self.stop()
        if self._program is None:
            self.error.emit(
                "Audio playback requires ffplay (from FFmpeg) or mpv. "
                "Install one of them and restart OmniReader."
            )
            return
        self._stopping = False
        self._elapsed_ms = 0
        self._started_at = time.monotonic()
        self._process.setProgram(str(self._program))
        self._process.setArguments([*self._base_arguments, "--", str(path)])
        self._process.start()
        if not self._process.waitForStarted(3_000):
            self._started_at = None
            self.error.emit(
                f"Could not start audio player {self._program.name}: "
                f"{self._process.errorString()}"
            )
            return
        self._timer.start()

    def resume(self) -> None:
        if (
            self._process.state() == QProcess.ProcessState.Running
            and self._started_at is None
        ):
            self._send_signal(signal.SIGCONT)
            self._started_at = time.monotonic()
            self._timer.start()

    def pause(self) -> None:
        if (
            self._process.state() == QProcess.ProcessState.Running
            and self._started_at is not None
        ):
            self._update_elapsed()
            self._started_at = None
            self._timer.stop()
            self._send_signal(signal.SIGSTOP)
            self.position_changed.emit(self._elapsed_ms)

    def stop(self) -> None:
        self._timer.stop()
        self._started_at = None
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._stopping = True
            self._process.terminate()
            if not self._process.waitForFinished(1_000):
                self._process.kill()
                self._process.waitForFinished(1_000)

    def _send_signal(self, value: signal.Signals) -> None:
        process_id = self._process.processId()
        if process_id > 0 and hasattr(os, "kill"):
            with suppress(ProcessLookupError):
                os.kill(process_id, value)

    def _update_elapsed(self) -> None:
        if self._started_at is not None:
            self._elapsed_ms += round((time.monotonic() - self._started_at) * 1_000)
            self._started_at = time.monotonic()

    def _emit_position(self) -> None:
        self._update_elapsed()
        self.position_changed.emit(self._elapsed_ms)

    def _process_finished(
        self, exit_code: int, _exit_status: QProcess.ExitStatus
    ) -> None:
        self._timer.stop()
        self._update_elapsed()
        self._started_at = None
        if self._stopping:
            self._stopping = False
            return
        if exit_code == 0:
            self.finished.emit()
            return
        detail = (
            bytes(self._process.readAllStandardError()).decode(errors="replace").strip()
        )
        message = detail or self._process.errorString()
        self.error.emit(f"Audio playback failed: {message}")

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        if (
            not self._stopping
            and self._process.state() == QProcess.ProcessState.NotRunning
        ):
            self.error.emit(f"Audio player error: {self._process.errorString()}")
