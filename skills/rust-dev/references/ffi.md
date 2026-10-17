# FFI: calling C and being called from C

FFI is where Rust's guarantees stop at the boundary: the compiler can't check what the other side does with a pointer. So the work is to make that boundary as small, explicit and well-documented as possible, and to give the rest of the program a safe API in front of it.

## Contents
- Structure
- Verified example (both directions)
- Rules at the boundary
- Generating bindings and headers
- Linking
- Testing

## Structure

- **Wrapping a C library:** two crates, following the Rust convention. `foo-sys` holds the raw `unsafe extern "C"` declarations (usually generated) and the build script that links the library. `foo` depends on it and exposes a safe, idiomatic API: owned types with `Drop`, `Result` errors, slices instead of pointer and length pairs. Nothing outside `foo` touches `foo-sys`. Generated bindings break many lints, and the `-sys` crate can relax its own lint table because it contains nothing hand-written.
- **Exposing Rust to C:** one module (or crate, built as `cdylib` or `staticlib`) holds every `extern "C"` function, opted in with `#[expect(unsafe_code, reason = "...")]`. Each exported function is a thin shim: check pointers, convert to Rust types, call ordinary safe Rust, convert the result to a status code.
- Either way, the unsafe rule in [code-standards.md](code-standards.md) applies in full: a SAFETY comment per unsafe operation, a `# Safety` section on every unsafe function stating the caller's obligations.

## Verified example

This module compiles under the lint set in [code-standards.md](code-standards.md), and its tests pass. It was also built as a `cdylib` and called from a C program, which got the expected results, and valgrind reported no memory errors or leaks across the boundary.

```rust
//! FFI in both directions, with the unsafe confined to this module's boundary.
#![expect(
    unsafe_code,
    reason = "FFI boundary: calls into libc and exports a C API"
)]

use core::ffi::{CStr, c_char, c_int};

// ---- Calling C ------------------------------------------------------------------

unsafe extern "C" {
    // Stays unsafe to call: strlen reads until it finds a NUL, so a bad pointer is
    // undefined behavior. The `&CStr` wrapper below supplies that guarantee instead.
    fn strlen(s: *const c_char) -> usize;
}

/// Length of a C string, through libc. The `&CStr` type guarantees the pointer is valid
/// and NUL-terminated, which is everything `strlen` requires.
#[must_use]
pub fn c_len(s: &CStr) -> usize {
    // SAFETY: `s.as_ptr()` points to a valid NUL-terminated string that outlives the call.
    unsafe { strlen(s.as_ptr()) }
}

// ---- Exposing a C API -----------------------------------------------------------

/// Opaque to C: callers only ever hold a pointer from `counter_new`.
#[derive(Debug, Default)]
pub struct Counter {
    total: u64,
}

/// Status codes returned across the boundary. C has no `Result`, so every fallible
/// function returns one of these and writes outputs through pointers.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Ok = 0,
    NullPointer = 1,
    Overflow = 2,
}

/// Creates a counter. Free it with `counter_free`, never with C's `free`: memory goes
/// back to the allocator that produced it.
#[unsafe(no_mangle)]
pub extern "C" fn counter_new() -> *mut Counter {
    Box::into_raw(Box::default())
}

/// Frees a counter. Null is accepted and ignored, like C's `free`.
///
/// # Safety
///
/// `counter` must be null or a pointer from `counter_new` that hasn't been freed.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn counter_free(counter: *mut Counter) {
    if !counter.is_null() {
        // SAFETY: non-null, and by this function's contract it came from `Box::into_raw`
        // in `counter_new` and is freed only once.
        drop(unsafe { Box::from_raw(counter) });
    }
}

/// Adds `amount` and writes the new total to `out_total`.
///
/// # Safety
///
/// `counter` must be null or a live pointer from `counter_new`, not used from another
/// thread during the call. `out_total` must be null or valid for writing a `u64`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn counter_add(
    counter: *mut Counter,
    amount: u64,
    out_total: *mut u64,
) -> Status {
    // SAFETY: by the contract, `counter` is null (handled by `as_mut`) or a live, unaliased Counter.
    let Some(counter) = (unsafe { counter.as_mut() }) else {
        return Status::NullPointer;
    };
    // SAFETY: by the contract, `out_total` is null (handled by `as_mut`) or valid for writes.
    let Some(out_total) = (unsafe { out_total.as_mut() }) else {
        return Status::NullPointer;
    };
    let Some(total) = counter.total.checked_add(amount) else {
        return Status::Overflow;
    };
    counter.total = total;
    *out_total = total;
    Status::Ok
}

/// C enums arrive as plain integers. Converting into a Rust enum without checking is
/// undefined behavior for out-of-range values, so validate first.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    Fast = 0,
    Safe = 1,
}

impl TryFrom<c_int> for Mode {
    type Error = Status;
    fn try_from(raw: c_int) -> Result<Self, Status> {
        match raw {
            0 => Ok(Self::Fast),
            1 => Ok(Self::Safe),
            _ => Err(Status::Overflow),
        }
    }
}
```

The C side it was tested with:

```c
typedef struct Counter Counter;                     /* opaque: C never sees the fields */
typedef enum { Ok = 0, NullPointer = 1, Overflow = 2 } Status;
Counter *counter_new(void);
void counter_free(Counter *);
Status counter_add(Counter *, uint64_t, uint64_t *);
```

## Rules at the boundary

- **Opaque handles, not shared structs,** for anything with invariants. C gets a pointer to a type it can't see into, plus functions to create, use and free it. Shared `#[repr(C)]` structs are for plain data only.
- **Memory goes back to the allocator that produced it.** Rust allocates, so Rust frees, through an exported `_free` function. C allocates, so C frees. Mixing allocators corrupts the heap.
- **Every pointer can be null or dangling.** Check null with `as_ref`/`as_mut` and return a status. What can't be checked (dangling, wrong type, aliased) goes in the `# Safety` contract.
- **Pointer and length always travel together** for buffers. Turn them into a slice once at the boundary (`core::slice::from_raw_parts`, with a SAFETY comment covering null, alignment, length and lifetime), and work with the slice after that.
- **Validate enums and booleans from C.** An out-of-range value in a Rust `enum` or `bool` is undefined behavior the moment it exists. Take `c_int` and convert with `TryFrom`, as `Mode` does.
- **Strings:** `&CStr` from C pointers (`CStr::from_ptr` in an unsafe block, after the null check), and treat the bytes as not necessarily UTF-8 (`to_str()` returns a `Result`). For strings going out, prefer writing into a caller-provided buffer with a length over returning allocated strings, so no allocator ownership crosses the boundary.
- **No panic crosses the boundary.** A panic unwinding out of an `extern "C"` function aborts the process (Rust 1.81 and later). Under the no-panic rule that shouldn't happen, but the shim layer is where it would surface. Use `extern "C-unwind"` only when the C side is built to handle unwinding, which is rare.
- **Errors become status codes,** with details available through an out-parameter or a `last_error` function if C callers need them.
- **Callbacks** take an `Option<unsafe extern "C" fn(...)>` (C's function pointers can be null) and a `*mut c_void` user-data pointer that is passed back unchanged.
- **Threads:** say in the docs whether a handle may be used from several threads, and match it with the Rust type's `Send`/`Sync`.
- **Types from `core::ffi`** (`c_int`, `c_char`, `c_void`), never Rust's `i32` for C's `int`, so the code stays correct on platforms where they differ.

## Generating bindings and headers

- **bindgen** (Rust bindings from C headers) needs libclang. Run it as a command when the C header changes and commit the output into the `-sys` crate, rather than running it from `build.rs`. Every developer and CI machine then builds without libclang, and changes to the bindings show up in code review. A small script in the repository regenerates them.
- **cbindgen** (C headers from Rust) the same way: generate the header with the command-line tool, commit it, and check in CI that regenerating it produces no diff.
- Both are tools that run outside the build, not dependencies, so they don't need the dependency process. Pin their versions in the regeneration script.

## Linking

- `build.rs` in the `-sys` crate tells Cargo what to link: `println!("cargo::rustc-link-lib=foo");` and `println!("cargo::rustc-link-search=native=/path");`. Use `pkg-config` (with a `# why:`) where the platform provides `.pc` files.
- Add `links = "foo"` to the `-sys` crate's `[package]`, so Cargo refuses to link two different versions of the same native library.
- A `build.rs` that downloads or compiles C code needs a stronger reason than one that only links a system library: it runs code on every build machine and slows every clean build.

## Testing

- **The safe wrapper** gets ordinary tests, which exercise the unsafe code underneath.
- **Exported functions** are tested from Rust, calling them like C would, as the example's tests do, including null pointers and out-of-range values. Miri can run these tests when they don't call into foreign code.
- **Real calls into C** can't run under Miri. Run them under AddressSanitizer, or valgrind where sanitizers aren't available, when the FFI layer changes. See [verification.md](verification.md) for when that's required.
- **One C (or C++) test program** that links the built library and calls the API, run in CI, catches header and ABI mismatches that Rust-side tests can't see.
