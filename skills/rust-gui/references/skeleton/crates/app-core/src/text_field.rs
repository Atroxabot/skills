//! Single-line text editing: caret, selection and IME composition.
//! No windowing types, so it is unit-testable and reusable by any widget.

use std::ops::Range;

use unicode_segmentation::UnicodeSegmentation;

/// Editing state for one text field.
///
/// Invariant: `caret` and `anchor` are byte offsets on grapheme boundaries of `text`.
/// Every method keeps it, so slicing at them can't split a character.
#[derive(Debug)]
pub struct TextField {
    text: String,
    caret: usize,
    /// Where the selection started. Equal to `caret` when nothing is selected.
    anchor: usize,
    /// Text the IME is composing. Drawn at the caret, not part of `text` until committed.
    preedit: String,
    max_bytes: usize,
}

impl TextField {
    #[must_use]
    pub fn new(max_bytes: usize) -> Self {
        Self {
            text: String::new(),
            caret: 0,
            anchor: 0,
            preedit: String::new(),
            max_bytes,
        }
    }

    #[must_use]
    pub fn text(&self) -> &str {
        &self.text
    }

    #[must_use]
    pub fn preedit(&self) -> &str {
        &self.preedit
    }

    #[must_use]
    pub fn caret(&self) -> usize {
        self.caret
    }

    #[must_use]
    pub fn is_composing(&self) -> bool {
        !self.preedit.is_empty()
    }

    #[must_use]
    pub fn selection(&self) -> Option<Range<usize>> {
        (self.anchor != self.caret)
            .then(|| self.anchor.min(self.caret)..self.anchor.max(self.caret))
    }

    #[must_use]
    pub fn selected_text(&self) -> Option<&str> {
        self.selection().and_then(|range| self.text.get(range))
    }

    /// Inserts typed or pasted text at the caret, replacing the selection. Control
    /// characters are dropped, and input past `max_bytes` is cut at a character boundary.
    pub fn insert(&mut self, input: &str) {
        self.delete_selection();
        let room = self.max_bytes.saturating_sub(self.text.len());
        let mut accepted = String::new();
        for c in input.chars().filter(|c| !c.is_control()) {
            if accepted.len() + c.len_utf8() > room {
                break;
            }
            accepted.push(c);
        }
        if accepted.is_empty() || !self.text.is_char_boundary(self.caret) {
            return;
        }
        self.text.insert_str(self.caret, &accepted);
        self.caret += accepted.len();
        self.anchor = self.caret;
        debug_assert!(self.text.is_char_boundary(self.caret));
    }

    /// Removes the selection, or the grapheme before the caret.
    pub fn backspace(&mut self) {
        if self.delete_selection() {
            return;
        }
        if let Some(start) = self.prev_boundary() {
            self.remove(start..self.caret);
        }
    }

    /// Removes the selection, or the grapheme after the caret.
    pub fn delete_forward(&mut self) {
        if self.delete_selection() {
            return;
        }
        if let Some(end) = self.next_boundary() {
            self.remove(self.caret..end);
        }
    }

    pub fn move_left(&mut self, extend: bool) {
        let to = match self.selection() {
            // Without shift, Left collapses a selection to its start instead of moving.
            Some(range) if !extend => range.start,
            _ => self.prev_boundary().unwrap_or(self.caret),
        };
        self.set_caret(to, extend);
    }

    pub fn move_right(&mut self, extend: bool) {
        let to = match self.selection() {
            Some(range) if !extend => range.end,
            _ => self.next_boundary().unwrap_or(self.caret),
        };
        self.set_caret(to, extend);
    }

    pub fn home(&mut self, extend: bool) {
        self.set_caret(0, extend);
    }

    pub fn end(&mut self, extend: bool) {
        self.set_caret(self.text.len(), extend);
    }

    pub fn select_all(&mut self) {
        self.anchor = 0;
        self.caret = self.text.len();
    }

    /// Removes the selection and returns it, for the clipboard.
    pub fn cut(&mut self) -> Option<String> {
        let cut = self.selected_text().map(str::to_owned);
        self.delete_selection();
        cut
    }

    pub fn set_preedit(&mut self, text: &str) {
        self.preedit.clear();
        self.preedit.push_str(text);
    }

    pub fn commit(&mut self, text: &str) {
        self.preedit.clear();
        self.insert(text);
    }

    fn set_caret(&mut self, to: usize, extend: bool) {
        self.caret = to;
        if !extend {
            self.anchor = to;
        }
    }

    fn prev_boundary(&self) -> Option<usize> {
        let head = self.text.get(..self.caret)?;
        head.grapheme_indices(true).next_back().map(|(i, _)| i)
    }

    fn next_boundary(&self) -> Option<usize> {
        let tail = self.text.get(self.caret..)?;
        tail.graphemes(true).next().map(|g| self.caret + g.len())
    }

    fn delete_selection(&mut self) -> bool {
        match self.selection() {
            Some(range) => {
                self.remove(range);
                true
            }
            None => false,
        }
    }

    fn remove(&mut self, range: Range<usize>) {
        if self.text.is_char_boundary(range.start) && self.text.is_char_boundary(range.end) {
            self.text.replace_range(range.clone(), "");
            self.caret = range.start;
            self.anchor = range.start;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn field(text: &str) -> TextField {
        let mut f = TextField::new(1024);
        f.insert(text);
        f
    }

    #[test]
    fn backspace_removes_whole_grapheme() {
        // A family emoji is 5 chars joined by zero-width joiners; "é" here is e + combining accent.
        let mut f = field("a👨‍👩‍👧e\u{301}");
        f.backspace();
        assert_eq!(f.text(), "a👨‍👩‍👧");
        f.backspace();
        assert_eq!(f.text(), "a");
    }

    #[test]
    fn typing_replaces_selection() {
        let mut f = field("hello world");
        f.home(false);
        for _ in 0..5 {
            f.move_right(true);
        }
        assert_eq!(f.selected_text(), Some("hello"));
        f.insert("bye");
        assert_eq!(f.text(), "bye world");
        assert_eq!(f.caret(), 3);
    }

    #[test]
    fn preedit_is_not_text_until_committed() {
        let mut f = field("x");
        f.set_preedit("にほ");
        assert_eq!(f.text(), "x");
        assert!(f.is_composing());
        f.commit("日本");
        assert_eq!(f.text(), "x日本");
        assert!(!f.is_composing());
    }

    #[test]
    fn input_is_bounded_and_filtered() {
        let mut f = TextField::new(4);
        f.insert("ab\ncdéf");
        assert_eq!(f.text(), "abcd");
    }

    #[derive(Debug, Clone)]
    enum Op {
        Insert(String),
        Backspace,
        Delete,
        Left(bool),
        Right(bool),
        Home(bool),
        End(bool),
        Cut,
    }

    fn op() -> impl Strategy<Value = Op> {
        prop_oneof![
            "\\PC{0,4}".prop_map(Op::Insert),
            Just(Op::Backspace),
            Just(Op::Delete),
            any::<bool>().prop_map(Op::Left),
            any::<bool>().prop_map(Op::Right),
            any::<bool>().prop_map(Op::Home),
            any::<bool>().prop_map(Op::End),
            Just(Op::Cut),
        ]
    }

    proptest! {
        // Any sequence of edits keeps the caret and anchor on character boundaries and
        // inside the text, so no later slice can panic.
        #[test]
        fn edits_keep_the_invariant(ops in prop::collection::vec(op(), 0..64)) {
            let mut f = TextField::new(64);
            for op in ops {
                match op {
                    Op::Insert(s) => f.insert(&s),
                    Op::Backspace => f.backspace(),
                    Op::Delete => f.delete_forward(),
                    Op::Left(e) => f.move_left(e),
                    Op::Right(e) => f.move_right(e),
                    Op::Home(e) => f.home(e),
                    Op::End(e) => f.end(e),
                    Op::Cut => { f.cut(); }
                }
                prop_assert!(f.text.is_char_boundary(f.caret));
                prop_assert!(f.text.is_char_boundary(f.anchor));
                prop_assert!(f.text.len() <= 64);
            }
        }
    }
}
