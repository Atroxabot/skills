# Concurrency

## Contents
- Choosing the model
- Hot/cold threads with ring buffers (verified example)
- Making the hot path fast
- Memory ordering
- Async, when it's the right model
- Shared state and locks
- Shutdown and failure

## Choosing the model

Async is not faster by definition. It's a way to have many operations *waiting* at once without a thread each. A task waiting on a socket costs a few hundred bytes, and a thread costs a stack and a kernel object. That's the whole advantage. In return, async adds a runtime, a scheduler you don't control, cooperative scheduling (one slow task stalls others on its worker), cancellation at every `.await`, and latency jitter from work-stealing. For CPU work or a latency-critical pipeline those costs buy nothing.

Decide per project, from the workload, and write the decision and its reason in the project's README or design notes:

1. **Is one thread fast enough?** Many programs are. Sequential code is deterministic, easy to test and free of races. Measure before adding threads.
2. **CPU-bound and splittable?** Use `rayon` (`par_iter`, `par_chunks`), or `std::thread::scope` for a fixed handful of chunks. No channels or runtime needed.
3. **A pipeline with latency targets** (p99 in microseconds: trading, audio, control loops, packet processing, game simulation)? Use dedicated threads with a hot/cold split and ring buffers (below). Never on an async runtime: you can't bound latency on a scheduler you don't control.
4. **Thousands of concurrent, mostly waiting I/O operations** (an HTTP API, a proxy, a chat server)? Use async on tokio. See [services.md](services.md).
5. **Under a few hundred connections?** A thread per connection, or a small pool of threads doing blocking I/O, is usually simpler and at least as fast. Async becomes worth it as connection counts grow.
6. **Both?** Async (or blocking I/O threads) at the network edge, a ring buffer into synchronous hot threads, and a ring buffer back out. The edge is throughput-bound and the core is latency-bound, so they get different models.

## Hot/cold threads with ring buffers

The hot thread does only the latency-critical work. It is pinned to a core, it busy-polls its input, and in its loop it never allocates, takes a lock, logs, does I/O or makes a syscall: each of those can stall for an unbounded time. Everything slow (logging, metrics, persistence, notifications) is handed to cold threads through ring buffers, and the hot thread never waits on them. When the cold side is full, the hot side drops the item and counts the drop.

This module compiles under the lint set in [code-standards.md](code-standards.md) and was run end to end:

```rust
//! Hot/cold split: one pinned thread does the latency-critical work and never blocks,
//! never allocates, never takes a lock. Everything slow (logging, stats, disk) goes to a
//! cold thread over a ring buffer the hot thread can drop into without waiting.

use std::hint;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::thread::{self, JoinHandle};
use std::time::Duration;

/// Keeps a hot atomic on its own cache line so the cold thread's reads don't
/// bounce the line the hot thread writes to (false sharing).
#[repr(align(128))]
#[derive(Debug, Default)]
pub struct CachePadded<T>(pub T);

#[derive(Clone, Copy, Debug)]
pub struct Tick {
    pub price: u64,
    pub qty: u32,
}

#[derive(Clone, Copy, Debug)]
pub struct Event {
    pub notional: u64,
}

#[derive(Debug)]
pub struct Pipeline {
    pub input: rtrb::Producer<Tick>,
    pub dropped: Arc<CachePadded<AtomicU64>>,
    stop: Arc<AtomicBool>,
    hot: JoinHandle<()>,
    cold: JoinHandle<u64>,
}

#[derive(Debug)]
pub enum PipelineError {
    Spawn(std::io::Error),
    ThreadPanicked(&'static str),
}

impl std::fmt::Display for PipelineError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Spawn(_) => f.write_str("could not spawn a pipeline thread"),
            Self::ThreadPanicked(name) => write!(f, "the {name} thread panicked"),
        }
    }
}

impl std::error::Error for PipelineError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Spawn(e) => Some(e),
            Self::ThreadPanicked(_) => None,
        }
    }
}

impl Pipeline {
    /// `hot_core` is a core reserved for this process (isolated from the scheduler where the
    /// platform allows). Capacities are powers of two sized for the worst burst, measured.
    ///
    /// # Errors
    ///
    /// [`PipelineError::Spawn`] if the OS refuses to create either thread.
    pub fn start(hot_core: Option<core_affinity::CoreId>) -> Result<Self, PipelineError> {
        let (input, mut ticks) = rtrb::RingBuffer::<Tick>::new(1 << 16);
        let (mut events_tx, mut events_rx) = rtrb::RingBuffer::<Event>::new(1 << 12);
        let stop = Arc::new(AtomicBool::new(false));
        let dropped = Arc::new(CachePadded(AtomicU64::new(0)));

        let hot_stop = Arc::clone(&stop);
        let hot_dropped = Arc::clone(&dropped);
        let hot = thread::Builder::new()
            .name("hot".into())
            .spawn(move || {
                if let Some(core) = hot_core {
                    // Best effort: an unpinned hot thread is slower, not wrong.
                    let _pinned = core_affinity::set_for_current(core);
                }
                // Busy-poll: no syscalls, no parking. Burns one core by design.
                while !hot_stop.load(Ordering::Relaxed) {
                    let Ok(tick) = ticks.pop() else {
                        hint::spin_loop();
                        continue;
                    };
                    let event = Event {
                        notional: tick.price.saturating_mul(u64::from(tick.qty)),
                    };
                    // Never wait for the cold side. A full queue means it fell behind; count it.
                    if events_tx.push(event).is_err() {
                        hot_dropped.0.fetch_add(1, Ordering::Relaxed);
                    }
                }
            })
            .map_err(PipelineError::Spawn)?;

        let cold = thread::Builder::new()
            .name("cold".into())
            .spawn(move || {
                let mut total = 0_u64;
                loop {
                    match events_rx.pop() {
                        Ok(event) => total = total.wrapping_add(event.notional),
                        Err(_) if events_rx.is_abandoned() => return total,
                        // The cold side may sleep: latency here costs nothing.
                        Err(_) => thread::sleep(Duration::from_millis(1)),
                    }
                }
            })
            .map_err(PipelineError::Spawn)?;

        Ok(Self {
            input,
            dropped,
            stop,
            hot,
            cold,
        })
    }

    /// Stops the hot thread, lets the cold thread drain, and returns the cold total.
    ///
    /// # Errors
    ///
    /// [`PipelineError::ThreadPanicked`] if either thread panicked.
    pub fn shutdown(self) -> Result<u64, PipelineError> {
        // Relaxed is enough: the flag carries no data, and join() synchronizes.
        self.stop.store(true, Ordering::Relaxed);
        self.hot
            .join()
            .map_err(|_| PipelineError::ThreadPanicked("hot"))?;
        self.cold
            .join()
            .map_err(|_| PipelineError::ThreadPanicked("cold"))
    }
}
```

What to copy from it:
- **SPSC ring buffers** (`rtrb`) between exactly one producer and one consumer. They're the cheapest possible handoff: no locks, no allocation after creation, one cache-line transfer per item in the common case. Use `crossbeam-queue::ArrayQueue` only when several threads must share one queue.
- **Capacities are powers of two, sized for the worst measured burst.** Too small and the hot side drops, too large and the working set falls out of cache.
- **A backpressure policy is chosen per edge, explicitly.** Hot to cold: drop and count, since the hot path must never wait. Input to hot: the producer spins or blocks, since losing input is usually unacceptable. Never an unbounded queue: it hides overload until memory runs out.
- **The hot thread busy-polls** with `std::hint::spin_loop()`. Waking a parked thread takes tens of microseconds, which is longer than the whole latency budget in these systems. Busy-polling burns a core, so the core is reserved for it.
- **Cold threads may sleep or block.** Their latency costs nothing.
- **Counters are written by one thread and padded** to their own cache line (`CachePadded`), so readers don't slow the writer through false sharing.
- **Shutdown is explicit**: a stop flag for the hot thread, and the cold thread notices that its producer is gone (`is_abandoned`) and drains.

## Making the hot path fast

- **Pre-allocate everything** before the loop starts: buffers, pools, lookup tables. In the loop, memory is reused, never requested.
- **Pin the hot thread** (`core_affinity`) and keep the OS off that core. On Linux: the `isolcpus`, `nohz_full` and `rcu_nocbs` kernel parameters, IRQ affinity moved elsewhere, and the CPU governor set to `performance`. Document the deployment requirements next to the code.
- **Keep the working set in cache.** Plain structs in contiguous arrays, small hot structs with the cold fields moved elsewhere, no pointer chasing.
- **Batch.** Pop everything available and process it in one pass, instead of one item per loop iteration. Throughput rises and per-item overhead falls.
- **No `Arc` clones, `Box` allocations, `format!`, `HashMap` growth, logging or `Instant::now()` per item** unless measured to be fine. `Instant::now()` is a vDSO call on Linux and cheap, but not free.
- **Measure the tail, not the mean.** Record per-item latency into a fixed-bucket histogram (preallocated, written by the hot thread, read by a cold thread) and report p50, p99, p99.9 and max. A mean hides the stalls that matter.

## Memory ordering

Each atomic operation uses the weakest ordering that's correct, with a comment saying why:
- `Relaxed`: counters and flags that don't publish other data (statistics, a stop flag when `join` provides the synchronization).
- `Release` on the store that publishes data, paired with `Acquire` on the load that reads it: "everything I wrote before this store is visible to whoever sees this value".
- `AcqRel` for read-modify-write operations that both consume and publish.
- `SeqCst` only when you can name the property that needs a single global order (rare). It's not a safe default, just a slower one that hides the missing reasoning.

Hand-written lock-free structures are unsafe code under the unsafe rule: a dedicated module, SAFETY comments, and tests under Miri and ThreadSanitizer, and with `loom` for the ordering when it's subtle. Use `rtrb` or `crossbeam-queue` unless a measurement shows they're the bottleneck.

## Async, when it's the right model

- **tokio, with only the features used** (`rt-multi-thread`, `net`, `time`, `sync`, `macros`, `io-util`, `signal`), never `"full"`.
- **Build the runtime explicitly** (`tokio::runtime::Builder`) with named worker threads and a chosen worker count, instead of `#[tokio::main]` defaults that nobody decided.
- **Never block a worker.** CPU work over roughly 100 µs, blocking file I/O and blocking library calls go to `spawn_blocking`, a dedicated thread, or rayon. A blocked worker stalls every task queued on it.
- **No locks held across `.await`** (`await_holding_lock` is denied). Use `tokio::sync::Mutex` only when the lock really must be held across an await. Usually the fix is restructuring so it doesn't.
- **Bounded everything:** `mpsc::channel(n)` not `unbounded_channel`, a `Semaphore` or `JoinSet` limit on spawned tasks, timeouts on every network operation (`tokio::time::timeout`).
- **Know which futures are cancel-safe** before using them in `select!`. A `read` cancelled halfway can lose data. Keep state outside the future or use cancel-safe APIs.

## Shared state and locks

- Prefer ownership and message passing to shared mutable state. When state is shared, prefer a few coarse, short critical sections to many fine-grained locks.
- `std::sync::Mutex` and `RwLock` are fast (futex-based) and the right default. `parking_lot` needs a measured reason.
- Poisoning: with `panic = "abort"` a lock can't be poisoned, so `.lock().unwrap_or_else(PoisonError::into_inner)` is the idiom that satisfies the no-panic rule.
- Never hold a lock while calling unknown code (callbacks, trait objects from elsewhere): that's how deadlocks happen. Copy what you need, release, then call.
- Lock order is documented when more than one lock can be held at once.

## Shutdown and failure

- Every thread has a name (`thread::Builder::name`), so profilers, debuggers and panic messages say which one.
- Every spawned thread or task is joined or explicitly detached with a comment saying why. `JoinHandle`s dropped on the floor hide failures.
- Shutdown is ordered: stop accepting input, drain the queues, flush the cold side, then join. Each stage has a deadline.
- A thread that dies (join returns `Err`) is a bug: report it with the thread's name and exit non-zero, rather than limping on with part of the pipeline gone.
