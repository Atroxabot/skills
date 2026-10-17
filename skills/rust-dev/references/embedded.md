# Embedded and `no_std` firmware

Firmware is where the high-assurance rules matter most. There's often no one watching when it fails, it may control hardware, and updating it is expensive. The rules in [code-standards.md](code-standards.md) apply in full, with these additions.

## Structure

Firmware is always a workspace ([workspace.md](workspace.md)):

```
crates/
  <name>-core/    # #![no_std] logic: protocols, state machines, filters, control math. Tested on the host.
  <name>-fw/      # #![no_std] #![no_main] target crate: HAL setup, interrupts, tasks, wiring
```

The split is what makes firmware testable. Logic in `-core` takes plain values and traits (`embedded-hal` traits for peripherals), never concrete HAL types, so `cargo test -p <name>-core` runs on a laptop in milliseconds with property tests and fuzzing. The `-fw` crate stays thin.

`-fw` is built for the target (`.cargo/config.toml` sets `build.target` and the runner, such as `probe-rs run --chip <chip>`). The workspace's host test command excludes it: `cargo test --workspace --exclude <name>-fw`.

## Verified core example

Compiles for `thumbv7em-none-eabihf` and for the host under the lint set, and its tests pass on the host:

```rust
//! Firmware logic with no heap and no OS: builds for the target and tests on the host.
#![no_std]

use core::cell::Cell;
use critical_section::Mutex;

/// Moving average over the last `N` samples. Fixed size, no allocation, O(1) per sample.
#[derive(Debug)]
pub struct MovingAverage<const N: usize> {
    samples: [u16; N],
    next: usize,
    filled: usize,
    sum: u32,
}

impl<const N: usize> MovingAverage<N> {
    // Evaluated at compile time: a zero-sized window, or one whose sum could overflow
    // u32 (N * u16::MAX), fails the build instead of misbehaving at run time.
    const VALID: () = assert!(N > 0 && N <= 65_537, "window must be 1..=65537 samples");

    #[must_use]
    pub const fn new() -> Self {
        let () = Self::VALID;
        Self {
            samples: [0; N],
            next: 0,
            filled: 0,
            sum: 0,
        }
    }

    /// Adds a sample and returns the current average.
    pub fn push(&mut self, sample: u16) -> u16 {
        if let Some(slot) = self.samples.get_mut(self.next) {
            // In bounds of N * u16::MAX by VALID, so neither operation can overflow.
            self.sum = self.sum - u32::from(*slot) + u32::from(sample);
            *slot = sample;
        }
        self.next = if self.next + 1 == N { 0 } else { self.next + 1 };
        self.filled = (self.filled + 1).min(N);
        let filled = u32::try_from(self.filled).unwrap_or(u32::MAX);
        u16::try_from(self.sum / filled.max(1)).unwrap_or(u16::MAX)
    }
}

impl<const N: usize> Default for MovingAverage<N> {
    fn default() -> Self {
        Self::new()
    }
}

/// A counter shared between an interrupt handler and the main loop.
/// The critical section makes each read-modify-write atomic with respect to interrupts.
pub static OVERRUNS: Mutex<Cell<u32>> = Mutex::new(Cell::new(0));

pub fn record_overrun() {
    critical_section::with(|cs| {
        let count = OVERRUNS.borrow(cs);
        count.set(count.get().saturating_add(1));
    });
}

/// Parses a command line received over UART into at most 4 arguments, without allocating.
///
/// # Errors
///
/// Returns the input back if it has more than 4 arguments.
pub fn split_args(line: &str) -> Result<heapless::Vec<&str, 4>, &str> {
    let mut args = heapless::Vec::new();
    for word in line.split_ascii_whitespace() {
        args.push(word).map_err(|_| line)?;
    }
    Ok(args)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn average_of_partial_window() {
        let mut avg = MovingAverage::<4>::new();
        assert_eq!(avg.push(10), 10);
        assert_eq!(avg.push(20), 15);
    }

    #[test]
    fn average_drops_oldest() {
        let mut avg = MovingAverage::<2>::new();
        avg.push(100);
        avg.push(0);
        assert_eq!(avg.push(0), 0);
    }

    #[test]
    fn too_many_args_rejected() {
        assert!(split_args("a b c d e").is_err());
        assert_eq!(split_args("set led 1").unwrap().len(), 3);
    }
}
```

Host tests that call into `critical_section` need an implementation on the host: add `critical-section = { version = "1", features = ["std"] }` under `[dev-dependencies]`.

## Memory

- **No heap** by default: no `alloc`, no global allocator. All memory is static or on the stack, with sizes fixed at compile time, so the firmware can't fail from fragmentation or exhaustion at run time. Use `heapless` collections (`Vec<T, N>`, `String<N>`, `Deque<T, N>`), fixed arrays and const generics.
- If a heap is truly needed (a protocol stack that requires it), use a fixed-size heap from `embedded-alloc` (with a `# why:`), initialize it once at startup, and treat allocation failure as an error path.
- **Stack:** no recursion at all, no large arrays on the stack (make them `static` or put them in a task's state), and measure the worst-case stack with `cargo call-stack` or by painting the stack and checking the high-water mark. Use `flip-link` as the linker so a stack overflow faults instead of silently overwriting static data.
- **Const assertions for sizes:** `const _: () = assert!(size_of::<Frame>() <= 64);` fails the build, not the device. Compile-time asserts like this and `MovingAverage::VALID` are allowed under the no-panic rule, because they can't panic at run time.

## Concurrency and interrupts

- **No `static mut`.** Edition 2024 denies references to it, and it's how data races happen on single-core chips too (an interrupt can fire mid-update).
- Data shared with interrupt handlers lives in `critical_section::Mutex<Cell<T>>` or `Mutex<RefCell<T>>`, accessed inside `critical_section::with`. Keep critical sections short: they delay interrupts.
- Atomics (`AtomicU32` and friends) for single values on cores that support them. Cortex-M0/M0+ have no compare-and-swap, so use `portable-atomic` (with a `# why:`) or critical sections there.
- **A framework for structure** once there's more than a superloop with a couple of interrupts: `embassy` for async tasks on embedded (cooperative, no heap, low power by sleeping in the executor), or RTIC for interrupt-driven concurrency with priorities and compile-time-checked resource sharing. Either beats a hand-rolled scheduler.
- Interrupt handlers do the minimum (read the peripheral, push to a queue, set a flag) and return. Work happens in tasks or the main loop.

## Timing and determinism

- Hot control loops have a fixed period from a hardware timer, and their worst-case execution time is measured (toggle a GPIO and watch it on a scope or logic analyzer, or use the cycle counter `DWT::cycle_count()` on Cortex-M).
- Bounded loops only. Every wait on hardware (a flag that should become set) has a timeout or iteration limit and an error path, because hardware does fail.
- A **watchdog** is enabled in production and fed only from the main loop after all tasks have checked in. That way a hang in any task resets the device.
- Floating point only on chips with an FPU (`thumbv7em-none-eabihf`, not `eabi`), or use fixed-point arithmetic. Software float is slow and its timing varies.

## Panics

The no-panic rule holds, and the panic handler is the last line of defense, not error handling:
- Development: `panic-probe` prints the panic location over `defmt` and halts for the debugger.
- Production: a handler that records the location to a reserved RAM region or flash, puts outputs into a safe state (motors off, valves closed), and resets the device. After reset, firmware reports the stored panic.
- `panic = "abort"` in both profiles. `opt-level = "s"` or `"z"` when flash is tight, measured against `3`. `debug = true` costs nothing on the device (debug info stays on the host) and makes probe-rs backtraces useful.

## Logging and debugging

- `defmt` with `defmt-rtt`: formatting happens on the host, so log calls cost a few bytes and microseconds on the device instead of pulling in `core::fmt`, which is large and slow.
- `probe-rs` for flashing, running and debugging. Keep `cargo run` wired to it through the runner in `.cargo/config.toml`.
- Production builds keep a minimal log level. `defmt` levels are filtered at compile time with `DEFMT_LOG`.

## Testing

- `-core`: unit tests, property tests and fuzzing on the host. This is where most of the test effort goes.
- `-fw`: on-target tests with `embedded-test` or `defmt-test`, run through probe-rs on a real board in a hardware-in-the-loop CI job for anything touching peripherals, timing or interrupts.
- Unsafe code (register access outside the HAL, DMA buffers) follows the unsafe rule. For DMA especially, the SAFETY comment states who owns the buffer while the transfer runs.
