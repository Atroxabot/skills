//! Raw wgpu + winit: one pipeline, instanced quads, redraw only when needed.

mod dialogs;
mod error;
mod gpu;
mod input;

use std::process::ExitCode;
use std::sync::Arc;

use winit::application::ApplicationHandler;
use winit::dpi::{PhysicalPosition, PhysicalSize};
use winit::event::WindowEvent;
use winit::event_loop::{
    ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy, OwnedDisplayHandle,
};
use winit::keyboard::{Key, ModifiersState};
use winit::window::{Window, WindowId};

use crate::dialogs::UserEvent;
use crate::error::{AppError, Report};
use app_core::draw::Quad;

use crate::gpu::{Frame, Gpu};
use crate::input::Clipboard;
use app_core::text_field::TextField;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("error: {}", Report(&err));
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), AppError> {
    // A user-event loop, so background threads (dialogs, loading) can wake it with results.
    let event_loop = EventLoop::<UserEvent>::with_user_event()
        .build()
        .map_err(AppError::EventLoop)?;
    // Sleep until an event arrives. Idle UI costs zero CPU and GPU.
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App {
        display: event_loop.owned_display_handle(),
        proxy: event_loop.create_proxy(),
        state: None,
        failure: None,
        field: TextField::new(4096),
        clipboard: Clipboard::new(),
        modifiers: ModifiersState::empty(),
    };
    event_loop.run_app(&mut app).map_err(AppError::EventLoop)?;
    app.failure.map_or(Ok(()), Err)
}

struct App {
    display: OwnedDisplayHandle,
    proxy: EventLoopProxy<UserEvent>,
    state: Option<(Arc<Window>, Gpu)>,
    // winit callbacks can't return errors, so the first one is stored and the loop exits.
    failure: Option<AppError>,
    field: TextField,
    clipboard: Clipboard,
    modifiers: ModifiersState,
}

impl App {
    fn fail(&mut self, event_loop: &ActiveEventLoop, err: AppError) {
        self.failure.get_or_insert(err);
        event_loop.exit();
    }
}

impl ApplicationHandler<UserEvent> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.state.is_some() {
            return;
        }
        let attrs = Window::default_attributes().with_title("gpucheck");
        let window = match event_loop.create_window(attrs) {
            Ok(window) => Arc::new(window),
            Err(err) => return self.fail(event_loop, AppError::Window(err)),
        };
        match pollster::block_on(Gpu::new(self.display.clone(), Arc::clone(&window))) {
            Ok(mut gpu) => {
                gpu.set_quads(&[Quad {
                    rect: [40.0, 40.0, 200.0, 120.0],
                    color: [0.2, 0.5, 0.9, 1.0],
                }]);
                // The text field has focus from the start here. In a real UI, IME is allowed only
                // while a text widget is focused, so shortcuts elsewhere don't open IME popups,
                // and the cursor area follows the caret so candidate lists appear next to it.
                window.set_ime_allowed(true);
                window.set_ime_cursor_area(
                    PhysicalPosition::new(40, 40),
                    PhysicalSize::new(200, 120),
                );
                window.request_redraw();
                self.state = Some((window, gpu));
            }
            Err(err) => self.fail(event_loop, err),
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some((window, gpu)) = self.state.as_mut() else {
            return;
        };
        let result = match event {
            WindowEvent::CloseRequested => {
                event_loop.exit();
                Ok(())
            }
            WindowEvent::Resized(size) => {
                gpu.resize(size.width, size.height);
                window.request_redraw();
                Ok(())
            }
            WindowEvent::RedrawRequested => {
                window.pre_present_notify();
                gpu.render().map(|frame| {
                    if frame == Frame::Retry {
                        window.request_redraw();
                    }
                })
            }
            WindowEvent::ModifiersChanged(mods) => {
                self.modifiers = mods.state();
                Ok(())
            }
            WindowEvent::KeyboardInput { event, .. }
                if self.modifiers.control_key()
                    && event.state.is_pressed()
                    && event.logical_key == Key::Character("o".into()) =>
            {
                dialogs::open_file(window, self.proxy.clone()).map_err(AppError::Dialog)
            }
            WindowEvent::KeyboardInput { event, .. } => {
                if input::key(&mut self.field, &mut self.clipboard, self.modifiers, &event) {
                    show_field(window, &self.field);
                }
                Ok(())
            }
            WindowEvent::Ime(event) => {
                if input::ime(&mut self.field, &event) {
                    show_field(window, &self.field);
                }
                Ok(())
            }
            _ => Ok(()),
        };
        if let Err(err) = result {
            self.fail(event_loop, err);
        }
    }

    fn user_event(&mut self, _event_loop: &ActiveEventLoop, event: UserEvent) {
        let UserEvent::FileChosen(path) = event;
        if let (Some(path), Some((window, _))) = (path, self.state.as_ref()) {
            window.set_title(&format!("opened {}", path.display()));
        }
    }
}

/// Until the app renders text, the window title shows the field: the caret as `|`,
/// or the IME composition in brackets at the caret.
fn show_field(window: &Window, field: &TextField) {
    let text = field.text();
    let (head, tail) = text.split_at_checked(field.caret()).unwrap_or((text, ""));
    let title = match field.preedit() {
        "" => format!("{head}|{tail}"),
        preedit => format!("{head}[{preedit}]{tail}"),
    };
    window.set_title(&title);
}
