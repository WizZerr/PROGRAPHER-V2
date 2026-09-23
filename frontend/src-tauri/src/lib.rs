use serde::Serialize;
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const ENGINE_HOST: &str = "127.0.0.1";
const ENGINE_START_TIMEOUT: Duration = Duration::from_secs(25);

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

struct EngineRuntimeState {
    child: Option<CommandChild>,
    port: u16,
    secret: String,
    status: String,
}

struct EngineState {
    runtime: Mutex<EngineRuntimeState>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct EngineInfo {
    host: String,
    port: u16,
    secret: String,
    status: String,
}

#[tauri::command]
fn get_engine_info(state: tauri::State<'_, EngineState>) -> EngineInfo {
    let runtime = state.runtime.lock().expect("engine state mutex poisoned");

    EngineInfo {
        host: ENGINE_HOST.to_string(),
        port: runtime.port,
        secret: runtime.secret.clone(),
        status: runtime.status.clone(),
    }
}

fn reserve_runtime_port() -> Result<u16, String> {
    let listener = TcpListener::bind((ENGINE_HOST, 0))
        .map_err(|e| format!("failed to reserve engine port: {e}"))?;

    let port = listener
        .local_addr()
        .map_err(|e| format!("failed to read engine port: {e}"))?
        .port();

    drop(listener);
    Ok(port)
}

fn health_check(port: u16) -> bool {
    let address: SocketAddr = match format!("{ENGINE_HOST}:{port}").parse() {
        Ok(address) => address,
        Err(_) => return false,
    };

    let mut stream = match TcpStream::connect_timeout(&address, Duration::from_millis(300)) {
        Ok(stream) => stream,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));

    let request =
        format!("GET /health HTTP/1.1\r\nHost: {ENGINE_HOST}:{port}\r\nConnection: close\r\n\r\n");

    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    // Do not wait for EOF. Some HTTP servers keep the socket alive long enough
    // for read_to_string() to hit our timeout even though the full health
    // response has already arrived. Read bounded chunks and return as soon as
    // the expected response is present.
    let mut response = Vec::with_capacity(2048);
    let mut buffer = [0_u8; 2048];

    loop {
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(read) => {
                response.extend_from_slice(&buffer[..read]);

                let text = String::from_utf8_lossy(&response);
                if text.contains("200 OK")
                    && (text.contains("\"status\":\"ok\"")
                        || text.contains("\"status\": \"ok\""))
                {
                    return true;
                }

                if response.len() >= 16 * 1024 {
                    break;
                }
            }
            Err(error)
                if matches!(
                    error.kind(),
                    std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                ) =>
            {
                break;
            }
            Err(_) => return false,
        }
    }

    let text = String::from_utf8_lossy(&response);
    text.contains("200 OK")
        && (text.contains("\"status\":\"ok\"")
            || text.contains("\"status\": \"ok\""))
}

fn wait_until_healthy(port: u16) -> bool {
    let started = Instant::now();

    while started.elapsed() < ENGINE_START_TIMEOUT {
        if health_check(port) {
            return true;
        }

        thread::sleep(Duration::from_millis(180));
    }

    false
}

fn start_packaged_engine(app: &tauri::AppHandle) -> Result<(CommandChild, u16, String), String> {
    let port = reserve_runtime_port()?;
    let secret = uuid::Uuid::new_v4().to_string();

    let command = app
        .shell()
        .sidecar("prographer-engine")
        .map_err(|e| format!("failed to resolve packaged engine sidecar: {e}"))?
        .args(["--host", ENGINE_HOST, "--port", &port.to_string()])
        .env("PROGRAPHER_ENGINE_SECRET", &secret);

    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to start packaged ProGrapher Engine: {e}"))?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    if cfg!(debug_assertions) {
                        println!("[engine] {}", String::from_utf8_lossy(&bytes).trim_end());
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    if cfg!(debug_assertions) {
                        eprintln!("[engine] {}", String::from_utf8_lossy(&bytes).trim_end());
                    }
                }
                CommandEvent::Error(message) => {
                    eprintln!("[engine] process error: {message}");
                }
                CommandEvent::Terminated(payload) => {
                    if cfg!(debug_assertions) {
                        println!(
                            "[engine] terminated: code={:?} signal={:?}",
                            payload.code, payload.signal
                        );
                    }
                }
                _ => {}
            }
        }
    });

    if !wait_until_healthy(port) {
        terminate_engine(child);
        return Err(format!(
            "Packaged ProGrapher Engine did not become healthy within {} seconds",
            ENGINE_START_TIMEOUT.as_secs()
        ));
    }

    println!("ProGrapher packaged sidecar ready: http://{ENGINE_HOST}:{port}");

    Ok((child, port, secret))
}

#[cfg(target_os = "windows")]
fn terminate_engine(child: CommandChild) {
    let pid = child.pid();

    // PyInstaller --onefile runs a parent process and an extracted child
    // process. Killing only the CommandChild PID can leave the other process
    // alive. taskkill /T terminates the full process tree.
    let tree_killed = std::process::Command::new("taskkill.exe")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .status()
        .map(|status| status.success())
        .unwrap_or(false);

    // Fallback to the Tauri handle if taskkill was unavailable or failed.
    if !tree_killed {
        let _ = child.kill();
    }
}

#[cfg(not(target_os = "windows"))]
fn terminate_engine(child: CommandChild) {
    // macOS/Linux behavior remains on the native sidecar kill path for now.
    // macOS will receive its own process-lifecycle validation on real hardware.
    let _ = child.kill();
}

fn stop_engine(state: &EngineState) {
    if let Ok(mut runtime) = state.runtime.lock() {
        if let Some(child) = runtime.child.take() {
            terminate_engine(child);
        }

        runtime.status = "stopped".to_string();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            app.manage(EngineState {
                runtime: Mutex::new(EngineRuntimeState {
                    child: None,
                    port: 0,
                    secret: String::new(),
                    status: "starting".to_string(),
                }),
            });

            // Do not block desktop startup on the packaged Python engine.
            // The window should render immediately while the engine warms up
            // in the background. Frontend API calls wait for status="ready".
            let app_handle = app.handle().clone();

            tauri::async_runtime::spawn_blocking(move || {
                match start_packaged_engine(&app_handle) {
                    Ok((child, port, secret)) => {
                        let state = app_handle.state::<EngineState>();

                        if let Ok(mut runtime) = state.runtime.lock() {
                            runtime.child = Some(child);
                            runtime.port = port;
                            runtime.secret = secret;
                            runtime.status = "ready".to_string();
                        };
                    }
                    Err(error) => {
                        eprintln!("[engine] startup failed: {error}");

                        let state = app_handle.state::<EngineState>();

                        if let Ok(mut runtime) = state.runtime.lock() {
                            runtime.status = format!("error:{error}");
                        };
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_engine_info])
        .build(tauri::generate_context!())
        .expect("error while building ProGrapher");

    app.run(|app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            let state = app_handle.state::<EngineState>();
            stop_engine(state.inner());
        }
    });
}
