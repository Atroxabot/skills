# Servers, daemons and network services

## First: which concurrency model?

Decide before writing code, using the table in [concurrency.md](concurrency.md), and write the decision down:

- **Thousands of concurrent connections, mostly waiting** (HTTP APIs, proxies, websockets, chat): async on tokio.
- **Tens to a few hundred connections:** a thread per connection or a fixed pool doing blocking I/O is simpler, has no runtime, and is often as fast. Use `std::net` and `std::thread`.
- **Latency-critical processing** (market data, telemetry, packet pipelines): network I/O at the edge (async or dedicated blocking threads), then ring buffers into pinned synchronous hot threads. The hot path never runs on runtime worker threads, because a work-stealing scheduler can't give latency guarantees.

## The async service skeleton

When tokio is the choice, this is the shape. It compiles under the lint set in [code-standards.md](code-standards.md) and was run: it echoes lines, rejects an oversized line, and shuts down cleanly on Ctrl-C with exit code 0.

```rust
//! Line-echo service: explicit runtime, bounded connections, timeouts, graceful shutdown.

use std::fmt;
use std::io;
use std::net::SocketAddr;
use std::process::ExitCode;
use std::sync::Arc;
use std::time::Duration;

use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tokio_util::sync::CancellationToken;

const MAX_CONNECTIONS: usize = 1024;
const MAX_LINE: u64 = 8 * 1024;
const IDLE_TIMEOUT: Duration = Duration::from_secs(30);
const DRAIN_DEADLINE: Duration = Duration::from_secs(10);

#[derive(Debug)]
enum StartError {
    Runtime(io::Error),
    Bind { addr: SocketAddr, source: io::Error },
}

impl fmt::Display for StartError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Runtime(_) => f.write_str("cannot start the async runtime"),
            Self::Bind { addr, .. } => write!(f, "cannot listen on {addr}"),
        }
    }
}

impl std::error::Error for StartError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Runtime(e) | Self::Bind { source: e, .. } => Some(e),
        }
    }
}

fn main() -> ExitCode {
    let addr = SocketAddr::from(([127, 0, 0, 1], 7000));
    match run(addr) {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            // One level of cause is all StartError has; deeper chains use the Report helper from errors.md.
            match std::error::Error::source(&err) {
                Some(cause) => eprintln!("error: {err}: {cause}"),
                None => eprintln!("error: {err}"),
            }
            ExitCode::FAILURE
        }
    }
}

fn run(addr: SocketAddr) -> Result<(), StartError> {
    // Worker count and thread names are decisions, not defaults.
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .thread_name("svc-worker")
        .enable_io()
        .enable_time()
        .build()
        .map_err(StartError::Runtime)?;
    runtime.block_on(serve(addr))
}

async fn serve(addr: SocketAddr) -> Result<(), StartError> {
    let listener = TcpListener::bind(addr)
        .await
        .map_err(|source| StartError::Bind { addr, source })?;
    let shutdown = CancellationToken::new();
    let permits = Arc::new(Semaphore::new(MAX_CONNECTIONS));
    let mut connections = JoinSet::new();

    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => break,
            accepted = listener.accept() => {
                let Ok((stream, _peer)) = accepted else { continue };
                // At the limit, new connections are refused instead of queued without bound.
                let Ok(permit) = Arc::clone(&permits).try_acquire_owned() else { continue };
                let token = shutdown.child_token();
                connections.spawn(async move {
                    let _held = permit;
                    tokio::select! {
                        () = token.cancelled() => {}
                        _ = handle(stream) => {}
                    }
                });
            }
            // Reap finished connections so the set doesn't grow with history.
            Some(_) = connections.join_next(), if !connections.is_empty() => {}
        }
    }

    shutdown.cancel();
    let drained = tokio::time::timeout(DRAIN_DEADLINE, async {
        while connections.join_next().await.is_some() {}
    })
    .await;
    if drained.is_err() {
        connections.abort_all();
    }
    Ok(())
}

async fn handle(stream: TcpStream) -> io::Result<()> {
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read).take(MAX_LINE);
    let mut line = Vec::with_capacity(256);
    loop {
        line.clear();
        reader.set_limit(MAX_LINE);
        let n = tokio::time::timeout(IDLE_TIMEOUT, reader.read_until(b'\n', &mut line))
            .await
            .map_err(|_| io::Error::from(io::ErrorKind::TimedOut))??;
        if n == 0 {
            return Ok(());
        }
        if !line.ends_with(b"\n") && reader.limit() == 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "line too long"));
        }
        write.write_all(&line).await?;
    }
}
```

What to copy from it:
- **tokio with only the features used**, never `"full"`: `default-features = false, features = ["rt-multi-thread", "net", "time", "sync", "macros", "io-util", "signal"]`. Each feature is code compiled and shipped.
- **An explicit runtime** with a chosen worker count and named threads, instead of `#[tokio::main]` defaults. Named threads show up in profilers and panics.
- **Every resource bounded:** connections (a `Semaphore`), line or body size (`take` with a limit), idle time (`timeout` on every read), shutdown time (a drain deadline). An unbounded resource is a denial-of-service waiting for a client to find it.
- **Overload is refused, not queued.** At the connection limit, new connections are dropped right away. A queue of waiting connections just turns overload into timeouts for everyone.
- **Graceful shutdown:** stop accepting, cancel connections through a `CancellationToken`, give them a deadline to finish, then abort what's left. The skeleton listens for Ctrl-C only. A deployed Unix service also selects on `tokio::signal::unix::signal(SignalKind::terminate())`, since `SIGTERM` is what service managers send.
- **Tasks are tracked** in a `JoinSet`, so none are lost and shutdown can wait for them.

## Rules for async code

- **Never block a worker.** Blocking file I/O, CPU work over about 100 µs, blocking library calls and `std::thread::sleep` go to `spawn_blocking` or a dedicated thread. One blocked worker stalls every task scheduled on it.
- **No `std::sync::Mutex` guard held across `.await`** (`await_holding_lock` is denied). Copy what you need out of the lock, drop the guard, then await.
- **Bounded channels** (`mpsc::channel(n)`), never `unbounded_channel`. Decide what happens when full: wait (backpressure to the producer), or `try_send` and reject.
- **Timeouts on every network operation**, including connects, TLS handshakes, reads, writes, and calls to other services. The default for a socket is to wait forever.
- **Cancel safety:** in `select!`, a branch that loses is dropped mid-operation. Know which futures can be dropped safely (`accept`, `recv` on tokio channels), and keep partial state (buffers) outside futures that can't.
- **Spawned tasks are owned:** a `JoinSet` or a stored `JoinHandle`, never fire-and-forget. A task that fails silently is a bug nobody sees.

## HTTP

- `hyper` for HTTP/1 and HTTP/2 at a low level. `axum` (built on hyper and tower) once there are more than a handful of routes, for routing and extractors.
- Limit request body size on every route (axum's `DefaultBodyLimit`, or `http_body_util::Limited`), header count and size, and request duration.
- TLS through `rustls` and `tokio-rustls`. Terminate TLS at a load balancer only when the network behind it is trusted, and say so in the deployment notes.
- Handlers parse the request into typed values first, call into `core` logic, and map errors to status codes in one place.

## Configuration

- Read once at startup from environment variables and/or a config file, parse into a typed `Config` struct, validate everything (ports, paths, limits, URLs), and fail at startup with a clear error. Never read the environment in the middle of request handling.
- Secrets come from the environment or a secrets file mounted at runtime, never from the repository or command-line arguments (visible in `ps`). Their `Debug` impl redacts them.

## Observability

- `tracing` with `tracing-subscriber`. Structured fields (`tracing::info!(peer = %addr, bytes = n, "request done")`), not formatted strings, so logs can be queried.
- A span per request or connection carrying its id, so every log line from it can be found together.
- Log an error once, where it's handled, with its full chain. Don't log at every layer.
- Levels: `error` needs a human, `warn` is degraded but working, `info` is lifecycle events (start, stop, config summary), `debug`/`trace` are off in production.
- Hot paths don't log per item. Count instead and export the counters.
- Expose health (process alive) and readiness (dependencies reachable, ready for traffic) separately.

## Daemons

- Run in the foreground and log to stderr. The service manager (systemd, a container runtime) handles backgrounding, restarts and log collection. Don't write your own daemonization or PID files.
- Handle `SIGTERM` like Ctrl-C: graceful shutdown with a deadline shorter than the manager's kill timeout.
- Treat a crash as a restart, not a disaster: state that must survive goes to durable storage, written atomically (temporary file plus `rename`, or a database transaction).

## Testing

- Core logic in `<name>-core` with unit and property tests, no network.
- Protocol parsing with fuzz targets ([verification.md](verification.md)).
- Integration tests that bind to port 0 (the OS picks a free port), run the real server in the test, and connect with a real client. Cover the limits: oversized input, slow clients that hit the idle timeout, the connection cap, shutdown while requests are in flight.
- Load tests for latency under load (p50, p99, p99.9) before release, on hardware like production.
