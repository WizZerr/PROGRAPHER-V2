use serde::Serialize;
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;

const ENGINE_HOST: &str = "127.0.0.1";
const ENGINE_START_TIMEOUT: Duration = Duration::from_secs(15);

struct EngineState {
    child: Mutex<Option<Child>>,
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

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
}

fn backend_dir() -> PathBuf {
    project_root().join("backend")
}

#[cfg(target_os = "windows")]
fn python_executable() -> PathBuf {
    backend_dir().join(".venv").join("Scripts").join("python.exe")
}

#[cfg(not(target_os = "windows"))]
fn python_executable() -> PathBuf {
    backend_dir().join(".venv").join("bin").join("python")
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

    let _ = stream.set_read_timeout(Some(Duration::from_millis(700)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(700)));

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

        thread::sleep(Duration::from_millis(150));
    }

    false
}

fn start_engine() -> Result<(Child, u16, String), String> {
    let python = python_executable();
    let backend = backend_dir();

    if !python.exists() {
        return Err(format!(
            "Python virtual environment was not found at: {}",
            python.display()
        ));
    }

    if !backend.join("app").join("main.py").exists() {
        return Err(format!(
            "ProGrapher backend was not found at: {}",
            backend.display()
        ));
    }

    let port = reserve_runtime_port()?;
    let secret = uuid::Uuid::new_v4().to_string();

    let mut command = Command::new(&python);
    command
        .current_dir(&backend)
        .arg("-m")
        .arg("uvicorn")
        .arg("app.main:app")
        .arg("--host")
        .arg(ENGINE_HOST)
        .arg("--port")
        .arg(port.to_string())
        .env("PROGRAPHER_ENGINE_SECRET", &secret);

    if cfg!(debug_assertions) {
        command.stdout(Stdio::inherit()).stderr(Stdio::inherit());
    } else {
        command.stdout(Stdio::null()).stderr(Stdio::null());
    }

    let mut child = command
        .spawn()
        .map_err(|e| format!("failed to start ProGrapher Engine: {e}"))?;

    if !wait_until_healthy(port) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(format!(
            "ProGrapher Engine did not become healthy within {} seconds",
            ENGINE_START_TIMEOUT.as_secs()
        ));
    }

    println!("ProGrapher Engine ready: http://{ENGINE_HOST}:{port}");

    Ok((child, port, secret))
}

fn stop_engine(state: &EngineState) {
    if let Ok(mut child_guard) = state.child.lock() {
        if let Some(child) = child_guard.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }

        *child_guard = None;
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let (child, port, secret) = start_engine()
                .map_err(|message| std::io::Error::other(message))?;

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
