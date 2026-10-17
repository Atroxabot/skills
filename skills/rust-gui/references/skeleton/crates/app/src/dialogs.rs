//! Native file dialogs that don't freeze the frame loop.

use std::io;
use std::path::PathBuf;
use std::thread;

use winit::event_loop::EventLoopProxy;
use winit::window::Window;

/// Results from background work, delivered to the event loop as user events.
#[derive(Debug)]
pub(crate) enum UserEvent {
    FileChosen(Option<PathBuf>),
}

/// Opens an "open file" dialog. It is started on the event-loop thread (macOS requires
/// that) and awaited on a helper thread, so the window keeps redrawing while it's open.
/// The choice comes back as [`UserEvent::FileChosen`].
pub(crate) fn open_file(window: &Window, proxy: EventLoopProxy<UserEvent>) -> io::Result<()> {
    let dialog = rfd::AsyncFileDialog::new()
        .set_parent(window)
        .add_filter("Images", &["png", "jpg"])
        .pick_file();
    thread::Builder::new()
        .name("file-dialog".into())
        .spawn(move || {
            let path = pollster::block_on(dialog).map(|file| file.path().to_path_buf());
            // Fails only when the event loop has already exited; nobody is left to tell.
            let _ignored = proxy.send_event(UserEvent::FileChosen(path));
        })?;
    Ok(())
}
