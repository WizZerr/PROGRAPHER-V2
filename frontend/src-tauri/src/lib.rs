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

const ENGINE_HOST: &str = "127.0.0.1";
const ENGINE_START_TIMEOUT: Duration = Duration::from_secs(25);

struct EngineState {
    child: Mutex<Option<CommandChild>>,
    port: u16,
    secret: String,
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
    EngineInfo {
        host: ENGINE_HOST.to_string(),
        port: state.port,
        secret: state.secret.clone(),
        status: "ready".to_string(),
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

    let request = format!(
        "GET /health HTTP/1.1\r\nHost: {ENGINE_HOST}:{port}\r\nConnection: close\r\n\r\n"
    );

    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    response.contains("200 OK") && response.contains("\"status\":\"ok\"")
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

fn start_packaged_engine(
    app: &tauri::AppHandle,
) -> Result<(CommandChild, u16, String), String> {
    let port = reserve_runtime_port()?;
    let secret = uuid::Uuid::new_v4().to_string();

    let command = app
        .shell()
        .sidecar("prographer-engine")
        .map_err(|e| format!("failed to resolve packaged engine sidecar: {e}"))?
        .args([
            "--host",
            ENGINE_HOST,
            "--port",
            &port.to_string(),
        ])
        .env("PROGRAPHER_ENGINE_SECRET", &secret);

    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to start packaged ProGrapher Engine: {e}"))?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    if cfg!(debug_assertions) {
                        println!(
                            "[engine] {}",
                            String::from_utf8_lossy(&bytes).trim_end()
                        );
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    if cfg!(debug_assertions) {
                        eprintln!(
                            "[engine] {}",
                            String::from_utf8_lossy(&bytes).trim_end()
                        );
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
        let _ = child.kill();
        return Err(format!(
            "Packaged ProGrapher Engine did not become healthy within {} seconds",
            ENGINE_START_TIMEOUT.as_secs()
        ));
    }

    println!(
        "ProGrapher packaged sidecar ready: http://{ENGINE_HOST}:{port}"
    );

    Ok((child, port, secret))
}

fn stop_engine(state: &EngineState) {
    if let Ok(mut child_guard) = state.child.lock() {
        if let Some(child) = child_guard.take() {
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let (child, port, secret) = start_packaged_engine(app.handle())
                .map_err(std::io::Error::other)?;

            app.manage(EngineState {
                child: Mutex::new(Some(child)),
                port,
                secret,
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
