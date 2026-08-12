# OmniReader — Technical Specification

## 1. Overview

A desktop application for Linux that reads documents aloud using either a cloud
TTS API (Microsoft Edge "Read Aloud" API via `edge-tts`) or a local/offline TTS
library (Piper), with automatic fallback, word/sentence-level highlighting
synced to speech, bookmarks, persistent reading position, optional content
filtering (hidden text, headers/footers), and a tabbed interface for multiple
open documents.

**Stack:** Python 3.10+, PySide6 (Qt for Python).

## 2. Goals

- Support two interchangeable TTS backends behind a common interface:
  - **Edge backend**: `edge-tts` (unofficial Microsoft Edge Read Aloud API client), high quality, requires network.
  - **Piper backend**: local ONNX voice models, works fully offline, good quality.
- User picks a **default backend** in settings. If the default is the Edge
  backend and the network is unavailable (or the API call fails), the app
  **automatically falls back** to Piper and notifies the user.
- Voice selection is **per-document, not just global** — each open document
  remembers its own chosen backend/voice/rate/pitch, overriding the global
  default, and that choice persists across sessions.
- **Word-level highlighting** synced to audio playback (sentence-level
  fallback when word timing isn't available).
- **Bookmarks** (user-created, named) and **automatic reading-position save/restore**
  per document.
- **Optional, user-controlled filters** to strip hidden text and header/footer
  content before reading.
- **Tabbed UI** — multiple documents open concurrently, each with independent
  playback/position state.
- Support common formats: `.txt`, `.md`, `.html`/`.htm`, `.docx`, legacy `.doc`,
  `.pdf`, `.epub`, `.rtf`.

## 3. Non-Goals (v1)

- Mobile/Windows/macOS packaging (Linux-first; code should stay portable but
  is not required to be tested elsewhere).
- Real-time collaborative reading / multi-user sync.
- Voice cloning or custom voice training.
- Editing document content (read-only viewer).
- Cloud sync of bookmarks/state across machines (local SQLite only in v1).

## 4. Architecture Overview

Layered design so backends and parsers are swappable and independently testable.

```
┌─────────────────────────────────────────────────────────────────┐
│  UI Layer (PySide6)                                              │
│  MainWindow → QTabWidget → ReaderTab (per document)               │
│  - DocumentView (highlight-capable text view)                    │
│  - PlaybackControls, BookmarkPanel, FilterPanel, SettingsDialog   │
└─────────────────────────────────────────────────────────────────┘
                │                          │
                ▼                          ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│  Document Layer            │   │  TTS Layer                    │
│  - Parsers (per format)    │   │  - TTSBackend ABC              │
│  - NormalizedDocument model│   │  - EdgeTTSBackend               │
│  - Filters (hidden/header/ │   │  - PiperTTSBackend              │
│    footer)                 │   │  - BackendManager (selection,  │
│  - Sentence/word segmenter │   │    fallback, network probe)    │
└───────────────────────────┘   └───────────────────────────────┘
                │                          │
                ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Playback/Sync Engine                                            │
│  - AudioPlayer (QMediaPlayer / sounddevice)                      │
│  - Word/sentence timing map, playback clock → highlight index    │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Persistence Layer                                                │
│  - SQLite (documents, bookmarks, reading_state, settings, tabs)  │
└─────────────────────────────────────────────────────────────────┘
```

## 5. TTS Backend Abstraction

### 5.1 Interface

```python
class WordTiming(NamedTuple):
    word_index: int      # index into NormalizedDocument.words
    start_ms: int         # offset from start of this synthesis chunk
    end_ms: int

class SynthesisResult(NamedTuple):
    audio_path: Path              # rendered audio (wav/mp3) for this chunk
    word_timings: list[WordTiming]  # empty if backend can't provide word-level timing
    sentence_only_timing: bool    # True if only sentence-level sync is possible

class TTSBackend(ABC):
    name: str
    requires_network: bool

    @abstractmethod
    def is_available(self) -> bool: ...
    """Cheap check: for Edge, a network probe + auth check; for Piper, model files present."""

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]: ...

    @abstractmethod
    def synthesize(
        self,
        text_chunk: TextChunk,      # one sentence or small group of sentences
        voice_id: str,
        rate: float,                 # 0.5–2.0
        pitch: float,                # backend-dependent range, normalized -1..1
    ) -> SynthesisResult: ...

    @abstractmethod
    def cancel(self) -> None: ...
```

### 5.2 EdgeTTSBackend

- Implemented on top of the `edge-tts` Python package (wraps Microsoft Edge's
  Read Aloud WebSocket API). No API key required, but it is an undocumented
  endpoint — the code must isolate this behind the interface so it can be
  swapped for an official API later with no changes elsewhere.
- `edge-tts` emits **word boundary events** (`WordBoundary`) with offsets —
  use these directly to populate `WordTiming`. This is the primary source of
  true word-level highlighting.
- `is_available()`: attempt a short DNS/HTTPS reachability check
  (`https://speech.platform.bing.com`) with a short timeout (~1.5s); treat
  timeout/DNS failure/HTTP error as unavailable.
- Network errors during an in-progress synthesis should raise a distinguishable
  `BackendUnavailableError` so `BackendManager` can trigger fallback mid-session.
- Output audio format: mp3 or wav from the API, transcoded to wav if needed for
  the audio player.

### 5.3 PiperTTSBackend

- Wraps the `piper` local TTS engine (ONNX voice models, run via `piper-tts`
  Python package or subprocess to the `piper` binary).
- Voice discovery: scan a configured models directory (default
  `~/.local/share/omnireader/piper-voices/`) for `.onnx` + `.onnx.json` pairs.
- **No native word-boundary events.** Two options, implement both, user-configurable:
  1. **Estimated timing (default, simple)**: distribute chunk audio duration
     across words proportional to character count (with small fixed pause
     padding at punctuation). Good enough for sentence-level highlight
     accuracy; word-level will drift slightly on long sentences.
  2. **Forced alignment (optional, higher quality)**: run the synthesized
     audio + text through a lightweight forced aligner (e.g. `aeneas` or a
     phoneme-duration-based approach using Piper's own eSpeak-ng phonemization
     output, which does expose per-phoneme timing) to get real word timing.
     Ship this as an optional dependency; degrade gracefully if not installed.
- `is_available()`: check at least one voice model exists locally.

### 5.4 BackendManager

- Holds the user's **default backend** (from settings) and the fallback order
  (currently fixed: Edge → Piper, but keep it a list for future backends).
- On document playback start: call `is_available()` on the default backend.
  - Available → use it.
  - Not available → use fallback, show a non-blocking toast/status-bar
    notice: *"Edge TTS unavailable (offline) — using Piper voice instead."*
- Mid-playback failure (e.g. network drops): catch `BackendUnavailableError`,
  switch to fallback **at the current sentence**, re-synthesize forward from
  there, show the same notice. Do not restart the whole document.
- Recovery: periodically (e.g. every 30s, low cost) re-probe the preferred
  backend in the background; if it becomes available again, show a subtle
  "Edge TTS available again — switch?" affordance rather than silently
  switching back (avoid disrupting playback/voice change mid-sentence).
- Emits Qt signals: `backend_changed(name, reason)`, `backend_unavailable(name)`.

## 6. Document Ingestion & Parsing

### 6.1 Normalized Document Model

All parsers convert their source format into a single internal representation
so the rest of the app (highlighting, filtering, TTS chunking) is format-agnostic.

```python
class Word(NamedTuple):
    text: str
    char_start: int   # offset into the block's plain text
    char_end: int

class Sentence(NamedTuple):
    words: list[Word]
    char_start: int
    char_end: int

class Block(NamedTuple):
    id: str
    kind: Literal["paragraph", "heading", "list_item", "header", "footer",
                   "hidden", "table_cell", "caption"]
    sentences: list[Sentence]
    plain_text: str
    source_ref: Any    # format-specific back-reference (e.g. docx element id,
                        # HTML DOM path, PDF page+bbox) for highlighting in
                        # the original rendered view if needed

class NormalizedDocument(NamedTuple):
    doc_id: str
    title: str
    blocks: list[Block]
    metadata: dict
```

- Sentence segmentation: use `syntok` or `nltk.punkt` (prefer `syntok` — no
  data download required) for robust sentence boundary detection.
- Word segmentation: simple whitespace/punctuation tokenizer, keep original
  offsets for exact highlighting (don't lose punctuation position).

### 6.2 Parsers by Format

| Format | Library | Notes |
|---|---|---|
| `.txt` | stdlib | Paragraphs split on blank lines |
| `.md` | `markdown-it-py` → walk token tree | Headings tagged as `heading`, code blocks excluded from reading by default (configurable) |
| `.html`/`.htm` | `BeautifulSoup4` + `lxml` | Strip `<script>`/`<style>`; detect `<header>`/`<footer>`/`nav`/`aside` tags and CSS `display:none`/`visibility:hidden`/`aria-hidden` for hidden-text filter |
| `.docx` | `python-docx` | Read headers/footers via `section.header`/`section.footer`; detect hidden runs via `run.font.hidden`; detect white-text-on-white or tiny font size as a heuristic (behind a filter toggle, off by default since heuristic) |
| `.doc` (legacy binary) | convert via `libreoffice --headless --convert-to docx` (subprocess) then reuse the docx parser | Document this external dependency clearly; detect at startup and warn if `soffice` is not installed |
| `.pdf` | `PyMuPDF` (`fitz`) | Use text extraction with position data; detect repeated text blocks at same page-relative y-position across pages as header/footer candidates; detect `render_mode`/invisible text (OCR text layers) as hidden-text candidate |
| `.epub` | `ebooklib` + the HTML parser above per chapter | Chapters become tabs-within-tab or a combined scroll — treat as one document with chapter-level blocks |
| `.rtf` | `striprtf` or convert via LibreOffice like `.doc` | |

Parsers all implement:

```python
class DocumentParser(ABC):
    supported_extensions: list[str]
    @abstractmethod
    def parse(self, path: Path) -> NormalizedDocument: ...
```

Registered in a `ParserRegistry` keyed by extension (+ MIME sniffing fallback
via `python-magic` for files with wrong/missing extensions).

## 7. Content Filters (Hidden Text, Headers/Footers)

- Each filter is a toggle in a **per-document Filter Panel**, defaulting to
  the user's global preference (set in Settings), but overridable per document
  and re-appliable at any time (does not require re-opening the file).
- Filters operate on `Block.kind` and metadata already tagged during parsing —
  filtering is just excluding blocks from the "read queue" and dimming them
  (not deleting) in the document view, so the user can see what's being
  skipped.
- Filter set (v1):
  - **Skip headers/footers** (default: ON) — blocks tagged `header`/`footer`.
  - **Skip hidden text** (default: ON) — blocks tagged `hidden` (explicit
    hidden attribute; high confidence).
  - **Skip likely-hidden text (heuristic)** (default: OFF) — tiny font size,
    white-on-white, etc.; off by default because it's heuristic and can
    false-positive.
  - **Skip code blocks** (Markdown/HTML, default: OFF).
  - **Skip captions/footnotes** (default: OFF).
- UI: checkboxes in a collapsible panel per tab; changing a filter re-computes
  the read queue immediately (if paused) or takes effect at the next sentence
  boundary (if playing), never mid-word.

## 8. Word/Sentence Highlighting

- The `DocumentView` (QTextEdit/QTextBrowser or a custom `QPlainTextEdit`
  subclass) maintains a mapping from `(block_id, char_start, char_end)` →
  `QTextCursor` selection, built once when the document is loaded/rendered.
- A `PlaybackClock` (driven by `QMediaPlayer.positionChanged` or a manual
  timer when using `sounddevice` streaming) maps current audio position (ms)
  within the current chunk to a `WordTiming` entry via binary search over the
  sorted timing list for that chunk.
- On each highlight tick (~50–100ms, throttled):
  - If word-level timings exist (Edge, or Piper+forced-alignment): highlight
    the current word (distinct style) and its containing sentence (lighter
    background), auto-scroll to keep it in view.
  - If only sentence-level timing exists (Piper estimated mode): highlight the
    whole current sentence only; no word highlight.
- Highlighting must not block the UI thread — do all mapping/lookup on the
  main thread but keep it O(log n) (bisect), audio decoding/synthesis stays
  off-thread (`QThread`/`asyncio` in a worker thread since `edge-tts` is async).

## 9. Playback Engine

- Pipeline: Document → chunked into sentences (or small sentence groups, e.g.
  up to ~300 chars, to keep TTS latency low) → synthesis queue → decoded audio
  → `QMediaPlayer` (backed by Qt Multimedia / GStreamer on Linux) for playback.
- **Look-ahead buffering**: synthesize N+1 chunk while N is playing, so there's
  no gap between sentences. Configurable buffer depth (default 2 chunks ahead).
- Controls: Play, Pause, Stop, Skip to next/previous sentence, Skip to next/
  previous paragraph, Jump to bookmark, Speed (0.5×–2.0×), Voice picker,
  seek-by-click-on-text (click any word in the view → jump playback there).
- Click-to-seek requires re-synthesizing from that sentence forward (discard
  buffered-ahead audio for the old position).

## 10. Bookmarks & Reading State

### 10.1 Data Model (SQLite, `~/.local/share/omnireader/library.db`)

```sql
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,       -- content hash or path hash
    path TEXT NOT NULL,
    title TEXT,
    format TEXT,
    added_at TIMESTAMP,
    last_opened_at TIMESTAMP
);

CREATE TABLE document_voice_prefs (
    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id),
    backend_name TEXT,             -- NULL = inherit global default backend
    voice_id TEXT,                 -- NULL = inherit global default voice for that backend
    rate REAL,                     -- NULL = inherit global default rate
    pitch REAL,                    -- NULL = inherit global default pitch
    updated_at TIMESTAMP
);

CREATE TABLE reading_state (
    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id),
    block_id TEXT,
    sentence_index INTEGER,
    word_index INTEGER,
    scroll_offset INTEGER,
    updated_at TIMESTAMP
);

CREATE TABLE bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT REFERENCES documents(doc_id),
    block_id TEXT,
    sentence_index INTEGER,
    word_index INTEGER,
    label TEXT,                    -- user-provided or auto ("Page 4, ¶2")
    note TEXT,
    created_at TIMESTAMP
);

CREATE TABLE open_tabs (
    tab_order INTEGER,
    doc_id TEXT REFERENCES documents(doc_id),
    is_active INTEGER
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT   -- JSON-encoded
);
```

- **Auto-save reading position**: on pause, on tab switch, on app close, and
  every ~15s during playback (debounced), write to `reading_state`.
- **Resume on open**: opening a document (double-click in library, or app
  restart re-opening tabs) restores `reading_state` and scrolls the view there;
  does not auto-play — user presses Play.
- **Bookmarks**: user can add a bookmark at the current position (toolbar
  button / keyboard shortcut) with an optional label/note; a Bookmarks panel
  per tab lists them, click to jump.
- **Per-document voice preference**: each `ReaderTab` has a voice picker
  (backend + voice + rate/pitch) in its playback controls, distinct from the
  global default set in Settings. Resolution order when a document is opened:
  1. Row in `document_voice_prefs` for this `doc_id`, if any non-null fields
     are set (fields left null fall back to step 2).
  2. Global default backend/voice/rate/pitch from `settings`.
  - Changing the voice picker in a tab writes/upserts `document_voice_prefs`
    immediately (debounced) so it's remembered next time that document is
    opened — including after switching tabs, closing the app, or reopening
    via "reopen tabs on startup."
  - Changing voice mid-playback behaves like the click-to-seek case in §9:
    finish the current chunk (or stop immediately, whichever feels less
    jarring — leave as a small config toggle), discard buffered look-ahead
    audio, and re-synthesize forward from the current sentence with the new
    voice.
  - If the document's preferred backend is unavailable, the existing
    `BackendManager` fallback logic in §5.4 still applies — the per-document
    preference just changes *which* backend/voice is "preferred" for that tab
    instead of always using the global default.
- `doc_id` should be a stable hash of file path (or content hash if the app
  should tolerate file moves — recommend content hash of first N KB + file
  size for v1, to survive renames/moves).

## 11. Tabbed Multi-Document UI

- `MainWindow` hosts a `QTabWidget` (closable, reorderable tabs, "+" button to
  open a file, middle-click to close).
- Each tab = a `ReaderTab` widget with its own: `DocumentView`, playback
  controls, filter panel, bookmark panel, and its own `BackendManager`/session
  state — **only one tab plays audio at a time**; opening/pressing play on
  another tab pauses the previous one (single shared audio output).
- On app close, persist the set of open tabs + their order + which was active
  (`open_tabs` table) and re-open them (without auto-playing) on next launch —
  configurable in Settings ("Reopen tabs on startup": on by default).
- File → Open (native file dialog, multi-select) and drag-and-drop onto the
  tab bar / window both supported.

## 12. Settings

Persisted in the `settings` table (JSON blob per key), exposed via a
`SettingsDialog`:

- **TTS**: default backend (Edge/Piper), default voice per backend, default
  rate/pitch, buffer depth, Piper voice-model directory, enable forced
  alignment for Piper (checkbox, with a note if dependency missing). These are
  **global fallback values** — per-document overrides (§10.2) take precedence
  when set, and each `ReaderTab` should offer a quick "reset to global
  default" action for its voice picker.
- **Filters**: global defaults for each filter in §7.
- **Reading**: reopen tabs on startup (on/off), auto-scroll during playback
  (on/off), highlight colors (word/sentence), font/size for the reading view.
- **Storage**: library DB location, cache directory for synthesized audio
  (with a "clear cache" button and a max-size setting — cache synthesized
  audio per document+voice+rate so re-reading doesn't re-synthesize).

## 13. Project Structure

```
omnireader/
├── main.py
├── ui/
│   ├── main_window.py
│   ├── reader_tab.py
│   ├── document_view.py
│   ├── playback_controls.py
│   ├── bookmark_panel.py
│   ├── filter_panel.py
│   └── settings_dialog.py
├── document/
│   ├── model.py            # NormalizedDocument, Block, Sentence, Word
│   ├── segmenter.py         # sentence/word segmentation
│   ├── filters.py
│   └── parsers/
│       ├── base.py
│       ├── txt.py
│       ├── markdown.py
│       ├── html.py
│       ├── docx.py
│       ├── legacy_doc.py    # libreoffice conversion wrapper
│       ├── pdf.py
│       ├── epub.py
│       └── rtf.py
├── tts/
│   ├── base.py               # TTSBackend ABC, data types
│   ├── edge_backend.py
│   ├── piper_backend.py
│   ├── alignment.py          # optional forced-alignment for Piper
│   └── backend_manager.py
├── playback/
│   ├── audio_player.py
│   ├── playback_clock.py
│   └── highlight_sync.py
├── persistence/
│   ├── db.py                 # SQLite schema + migrations
│   ├── documents_repo.py
│   ├── bookmarks_repo.py
│   └── settings_repo.py
└── tests/
    ├── document/
    ├── tts/
    └── playback/
```

## 14. Key Dependencies

- `PySide6` — UI, Qt Multimedia for audio playback
- `edge-tts` — Edge Read Aloud API client
- `piper-tts` (or `piper` binary via subprocess) — offline TTS
- `python-docx` — .docx parsing
- `PyMuPDF` (`fitz`) — .pdf parsing
- `beautifulsoup4` + `lxml` — HTML parsing
- `markdown-it-py` — Markdown parsing
- `ebooklib` — .epub parsing
- `striprtf` — .rtf parsing
- `syntok` — sentence segmentation
- `python-magic` — MIME sniffing fallback
- External (optional, feature-degrades if absent): `libreoffice` (legacy
  `.doc`/`.rtf` conversion), `aeneas` (forced alignment for Piper)

## 15. Suggested Implementation Phases

1. **Core skeleton**: main window, tabbed UI, open `.txt`/`.md` files, plain
   playback with one backend (Piper, since it needs no network to develop
   against), no highlighting yet.
2. **Backend abstraction**: add EdgeTTSBackend, BackendManager with fallback
   + network probing, voice/rate selection in UI.
3. **Highlighting**: word-boundary capture from Edge, sentence-level for
   Piper, `PlaybackClock` + `DocumentView` highlight sync.
4. **More parsers**: HTML, DOCX, PDF, EPUB, legacy DOC/RTF.
5. **Filters**: header/footer + hidden text detection per format, Filter Panel UI.
6. **Persistence**: SQLite schema, reading-position auto-save/resume, bookmarks.
7. **Polish**: tab session restore, audio caching, settings dialog, Piper
   forced-alignment (optional), keyboard shortcuts, click-to-seek.

## 16. Open Questions / Assumptions to confirm during implementation

- Assumed **no cloud account/API key needed** for the Edge backend (uses the
  same unauthenticated endpoint edge-tts relies on) — this is inherently
  fragile since it's an unofficial API; the interface must make it trivial to
  swap in a paid/official TTS API later without touching UI or persistence code.
- Assumed single-user, single-machine local app (no sync) for v1.
- Assumed read-only document viewing (no annotation beyond bookmarks/notes).
- Legacy `.doc`/`.rtf` support depends on LibreOffice being installed on the
  system; if that's not acceptable, flag it and we can look at
  `antiword`/`catdoc` or drop `.doc` support to plain-text-only extraction.
