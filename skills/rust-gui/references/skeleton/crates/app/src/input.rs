//! Routes winit keyboard and IME events to the focused text field.

use winit::event::{ElementState, Ime, KeyEvent};
use winit::keyboard::{Key, ModifiersState, NamedKey};

use app_core::text_field::TextField;

/// The OS clipboard, or nothing when it's unavailable (no display server, a sandbox).
/// Copy and paste then do nothing instead of failing the app.
pub(crate) struct Clipboard(Option<arboard::Clipboard>);

impl Clipboard {
    pub(crate) fn new() -> Self {
        // One instance for the app's lifetime: on X11 and Wayland the clipboard owner
        // must stay alive to serve pastes to other apps.
        Self(arboard::Clipboard::new().ok())
    }

    fn get(&mut self) -> Option<String> {
        self.0.as_mut()?.get_text().ok()
    }

    fn set(&mut self, text: String) {
        if let Some(clipboard) = self.0.as_mut() {
            // A failed copy isn't worth stopping for; a real app shows it in its status line.
            let _ignored = clipboard.set_text(text);
        }
    }
}

/// Applies a key press to the field. Returns true when the field changed and needs a redraw.
pub(crate) fn key(
    field: &mut TextField,
    clipboard: &mut Clipboard,
    mods: ModifiersState,
    event: &KeyEvent,
) -> bool {
    if event.state != ElementState::Pressed {
        return false;
    }
    let extend = mods.shift_key();
    let shortcut = if cfg!(target_os = "macos") {
        mods.super_key()
    } else {
        mods.control_key()
    };
    match &event.logical_key {
        Key::Named(NamedKey::Backspace) => field.backspace(),
        Key::Named(NamedKey::Delete) => field.delete_forward(),
        Key::Named(NamedKey::ArrowLeft) => field.move_left(extend),
        Key::Named(NamedKey::ArrowRight) => field.move_right(extend),
        Key::Named(NamedKey::Home) => field.home(extend),
        Key::Named(NamedKey::End) => field.end(extend),
        Key::Character(c) if shortcut => match c.to_ascii_lowercase().as_str() {
            "a" => field.select_all(),
            "c" => {
                if let Some(text) = field.selected_text() {
                    clipboard.set(text.to_owned());
                }
                return false;
            }
            "x" => {
                if let Some(text) = field.cut() {
                    clipboard.set(text);
                }
            }
            "v" => {
                if let Some(text) = clipboard.get() {
                    field.insert(&text);
                }
            }
            _ => return false,
        },
        // Composed text arrives through Ime::Commit. While the IME is composing, key text
        // belongs to the composition, so inserting it here would type it twice.
        _ => match &event.text {
            Some(text) if !shortcut && !field.is_composing() => field.insert(text),
            _ => return false,
        },
    }
    true
}

/// Applies an IME event. Returns true when the field changed and needs a redraw.
pub(crate) fn ime(field: &mut TextField, event: &Ime) -> bool {
    match event {
        // The cursor range inside the preedit is for drawing the composition caret.
        Ime::Preedit(text, _cursor) => field.set_preedit(text),
        Ime::Commit(text) => field.commit(text),
        Ime::Disabled => field.set_preedit(""),
        Ime::Enabled => return false,
    }
    true
}
