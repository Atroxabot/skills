# UI, text and OS integration

What a UI framework would otherwise provide: widgets and layout, text rendering, text input with input methods, the clipboard, file dialogs and accessibility. File paths refer to the skeleton in `skeleton/`.

## Contents
- Building the UI
- Text rendering
- Text input and IME
- Clipboard
- File dialogs
- Accessibility

## Building the UI

There's no framework, so the UI is ours, built in `app-core`. The structure that works:

1. **State** is plain Rust data owned by the app: the document, the selection, which panel is open, which widget has focus.
2. **Each frame** (that needs one), a build pass walks the state and produces widgets with layout constraints. Keep it simple: rows, columns, fixed and flexible sizes, padding, alignment. That covers most UIs without a general constraint solver.
3. **Layout** resolves sizes and positions into rectangles, top-down, in logical units. Cache layout of subtrees whose input didn't change when profiling shows layout as a cost.
4. **Hit-testing** uses the same rectangles: the topmost rectangle under the pointer that accepts input gets the event. Keep a per-frame list of interactive rectangles with **stable ids**, so hover, press and focus states persist across frames. The same ids become accessibility node ids if the app needs a screen reader tree.
5. **The draw list** is emitted in paint order: background quads, borders, images, glyphs, overlays. The renderer batches consecutive items of the same kind into one draw.
6. **Rounded corners, borders and shadows** come from signed distance functions in the fragment shader (per-instance corner radius, border width, blur), which gives anti-aliased edges with no MSAA and no extra geometry.
7. **Clipping** (scroll areas) uses scissor rectangles per batch, or a clip rectangle per instance tested in the shader when scissor changes would break batches.

## Text rendering

Text is the hardest part of a hand-built UI. Use a crate for shaping and rasterizing, and own the atlas and rendering:

- `fontdue` rasterizes glyphs and does simple layout. Enough for UIs in Latin, Cyrillic and Greek scripts with no ligatures or complex shaping.
- `cosmic-text` shapes (ligatures, Arabic, Indic, CJK fallback), handles bidirectional text and line breaking, and rasterizes through swash. Use it when the app shows user-provided text in any language, or rich text. It also includes an editor (`cosmic_text::Editor`) with caret, selection and grapheme handling for multi-line and bidirectional text, which replaces the skeleton's `TextField` for anything beyond single-line fields.

Either way: rasterize glyphs on demand into a GPU **glyph atlas** texture (a single-channel `R8Unorm` for coverage), cache by (font, glyph id, size, subpixel offset), and draw each glyph as an instanced quad sampling the atlas: the same pipeline shape as the skeleton, plus texture coordinates. Upload only newly rasterized glyphs each frame. Evict with a least-recently-used policy when the atlas fills, or grow it.

## Text input and IME

Typing text is more than reading key presses. Users of Chinese, Japanese, Korean and many other languages type through an **input method editor (IME)**: they type a phonetic composition, which the app shows inline (the *preedit*), and then pick the final characters from a candidate window. On macOS, even accented Latin letters typed with dead keys go through the IME. A text field that ignores this is unusable for a large share of the world.

What the skeleton does, and why:

- **The editing model lives in `app-core`** (`crates/app-core/src/text_field.rs` in the skeleton), with no winit types: insert, delete, caret movement, selection, preedit, commit. It's tested without a window, including a property test that runs random edit sequences and checks that the caret always stays on a character boundary.
- **Caret movement and deletion step by grapheme cluster**, not by `char` or byte, using `unicode-segmentation`. A family emoji is five `char`s joined by zero-width joiners, and "é" can be `e` plus a combining accent. Backspace must remove what the user sees as one character.
- **Input is bounded** (`max_bytes`) and control characters are dropped, so a paste of a huge or binary clipboard can't freeze or corrupt the field.
- **IME is allowed only while a text widget has focus** (`window.set_ime_allowed(true)` on focus, `false` on blur). While it's allowed, key presses can open IME popups, which is wrong for shortcuts on a canvas or in a game.
- **The IME cursor area follows the caret** (`window.set_ime_cursor_area(position, size)` after layout), so the candidate window appears next to the text instead of in a screen corner.
- **Events:** `Ime::Preedit(text, cursor)` replaces the shown composition (draw it at the caret, underlined, with its own cursor). `Ime::Commit(text)` inserts the final text. `Ime::Disabled` clears any preedit. Plain typing arrives as `KeyboardInput` with `event.text`, which is ignored while a composition is in progress so nothing is typed twice.
- **Shortcuts** use Command on macOS and Control elsewhere, and are matched on `logical_key` (the character the layout produces), so they work on non-QWERTY layouts.

IME behavior differs between platforms and input methods. Test text input on each target platform with a real IME (for example ibus or fcitx with a Japanese or Chinese engine on Linux, the built-in Japanese input on macOS and Windows), not only with a US keyboard.

## Clipboard

winit has no clipboard API. Use `arboard`, with `default-features = false, features = ["wayland-data-control"]`: the defaults pull in the whole `image` crate for image copy and paste, and the Wayland feature makes copy and paste work natively on Wayland rather than only through XWayland.

- Create **one** `arboard::Clipboard` for the app's lifetime. On X11 and Wayland, the app that copied must stay alive and keep its clipboard object to serve the data when another app pastes.
- Treat the clipboard as optional: creating it fails without a display server or in some sandboxes. The skeleton's `Clipboard` wrapper holds an `Option` and turns copy and paste into no-ops instead of failing the app.
- Pasted text goes through the same bounded, filtered `insert` as typing.

## File dialogs

Native open and save dialogs come from `rfd`. The rules:

- **Don't block the frame loop.** A blocking dialog call on the event-loop thread freezes the window while the dialog is open, and some desktops then flag the app as not responding. Use `rfd::AsyncFileDialog`: create the dialog on the event-loop thread (macOS requires dialogs to start on the main thread), await it on a helper thread with `pollster::block_on`, and send the result back as a user event through the `EventLoopProxy`. That's `crates/app/src/dialogs.rs` in the skeleton.
- **Set the parent window** (`set_parent`), so the dialog is modal to our window and appears on top of it.
- **Linux runtime dependencies:** rfd uses the XDG desktop portal, which needs a portal backend (GTK, GNOME or KDE) installed, and falls back to `zenity`. List them in the package dependencies.

## Accessibility

A hand-built UI is invisible to screen readers until we describe it. Decide at project start whether the app needs screen reader support (anything public-facing, anything used at work, anything with legal accessibility requirements does). Retrofitting it later means adding stable ids, roles and labels to every widget.

When it's needed, use `accesskit` with `accesskit_winit` (both on rust-dev's allowlist for this). The integration, from the accesskit_winit 0.34 API:

1. **Create the window hidden** (`Window::default_attributes().with_visible(false)`), create the adapter with `accesskit_winit::Adapter::with_event_loop_proxy(event_loop, &window, proxy)`, and only then call `window.set_visible(true)`. **The adapter panics if the window is already visible**, so this order isn't optional. The user event type implements `From<accesskit_winit::Event>`.
2. **Pass every `WindowEvent`** to `adapter.process_event(&window, &event)` before handling it.
3. **Build the tree from the same widget tree and stable ids the UI already has:** each widget becomes a node with a role (button, text input, list item), a label, its bounds and its state (focused, checked, disabled). Send changes with `adapter.update_if_active(|| tree_update)`. The closure only runs while an assistive technology is connected, so apps pay nothing when no screen reader is in use.
4. **Handle action requests** (focus, click, set value) that arrive as `accesskit_winit::Event`s, by routing them to the same code paths as mouse and keyboard input.

Weight: on Linux it adds the D-Bus stack that screen readers use (about 60 crates). If the app also uses tokio, enable `accesskit_winit`'s `tokio` feature in place of its default `async-io`, so there's one async runtime, not two.
