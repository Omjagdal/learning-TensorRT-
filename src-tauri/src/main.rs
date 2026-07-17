// src-tauri/src/main.rs
// =============================================================================
// ISRA Vision Chatbot — Tauri Shell
//
// Responsibilities:
//   1. Locate and spawn the Python backend_server sidecar
//   2. Read its stdout until "BACKEND_READY:<port>" is received
//   3. Open the native WebView2 window pointed at http://127.0.0.1:<port>
//   4. On window close, kill the sidecar process cleanly
// =============================================================================

// Prevents an extra console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager, WebviewWindow};

/// Shared state: holds the backend child process so we can kill it on exit.
struct BackendProcess(Mutex<Option<Child>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let app_handle = app.handle().clone();

            // Spawn backend in a background thread so we don't block the UI thread
            std::thread::spawn(move || {
                match spawn_backend(&app_handle) {
                    Ok(port) => {
                        // Backend is ready — show the window and navigate to it
                        let url = format!("http://127.0.0.1:{}", port);
                        println!("[Tauri] Backend is ready at {}", url);

                        if let Some(window) = app_handle.get_webview_window("main") {
                            // Navigate to the backend URL
                            let _ = window.navigate(url.parse().unwrap());
                            // Show the window (it starts hidden to avoid flash of empty content)
                            let _ = window.show();
                            let _ = window.set_focus();
                        } else {
                            eprintln!("[Tauri] ERROR: Could not find main window!");
                        }
                    }
                    Err(e) => {
                        eprintln!("[Tauri] FATAL: Backend failed to start: {}", e);
                        // Show an error dialog and exit
                        show_fatal_error(&app_handle, &e.to_string());
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill the Python sidecar when the user closes the window
                let state = window.state::<BackendProcess>();
                let mut guard = state.0.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    println!("[Tauri] Window closing — killing Python backend sidecar...");
                    let _ = child.kill();
                    let _ = child.wait();
                    println!("[Tauri] Backend sidecar terminated.");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

/// Locate, spawn, and monitor the Python backend sidecar.
/// Returns the port number once the backend signals BACKEND_READY:<port>.
fn spawn_backend(app_handle: &AppHandle) -> Result<u16, Box<dyn std::error::Error>> {
    let sidecar_path = find_sidecar(app_handle)?;
    println!("[Tauri] Launching backend sidecar: {:?}", sidecar_path);

    // Determine working directory: the sidecar directory
    let sidecar_dir = sidecar_path.parent().unwrap_or(&sidecar_path);

    let mut child = Command::new(&sidecar_path)
        .current_dir(sidecar_dir)
        .env("TAURI_SIDECAR", "1")
        .env("BACKEND_PORT", "8765")
        .stdout(Stdio::piped())
        .stderr(Stdio::null()) // loguru writes to stderr; suppress for clean stdout
        .spawn()?;

    let stdout = child
        .stdout
        .take()
        .ok_or("Could not capture backend stdout")?;

    // Store the child process so we can kill it on exit
    {
        let state = app_handle.state::<BackendProcess>();
        let mut guard = state.0.lock().unwrap();
        *guard = Some(child);
    }

    // Read lines from the backend stdout, waiting for BACKEND_READY:<port>
    let reader = BufReader::new(stdout);
    let timeout = Duration::from_secs(120); // 2 min max startup time
    let started = Instant::now();

    for line in reader.lines() {
        if started.elapsed() > timeout {
            return Err("Backend startup timed out after 2 minutes".into());
        }

        let line = line?;
        println!("[Backend] {}", line);

        if let Some(port_str) = line.strip_prefix("BACKEND_READY:") {
            let port: u16 = port_str
                .trim()
                .parse()
                .map_err(|_| format!("Invalid port in BACKEND_READY signal: {}", port_str))?;
            return Ok(port);
        }
    }

    Err("Backend process exited before signaling BACKEND_READY".into())
}

/// Find the backend_server sidecar executable.
/// In a Tauri bundle, resources are placed in the app's resources directory.
fn find_sidecar(app_handle: &AppHandle) -> Result<PathBuf, Box<dyn std::error::Error>> {
    // In production Tauri bundle: resources/backend_server/backend_server.exe
    let resource_dir = app_handle
        .path()
        .resource_dir()
        .map_err(|e| format!("Could not get resource dir: {}", e))?;

    let exe_name = if cfg!(target_os = "windows") {
        "backend_server.exe"
    } else {
        "backend_server"
    };

    let sidecar = resource_dir
        .join("backend_server")
        .join(exe_name);

    if sidecar.exists() {
        return Ok(sidecar);
    }

    // Development fallback: dist/backend_server/backend_server.exe
    let dev_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap_or(&PathBuf::from("."))
        .join("dist")
        .join("backend_server")
        .join(exe_name);

    if dev_path.exists() {
        println!("[Tauri] Dev mode: using sidecar at {:?}", dev_path);
        return Ok(dev_path);
    }

    Err(format!(
        "backend_server executable not found!\nLooked in:\n  {:?}\n  {:?}",
        sidecar, dev_path
    )
    .into())
}

/// Show a native OS error dialog with a fatal message, then exit.
fn show_fatal_error(app_handle: &AppHandle, message: &str) {
    eprintln!("[Tauri] FATAL ERROR: {}", message);
    // Write crash log to Desktop
    if let Ok(desktop) = app_handle.path().desktop_dir() {
        let log_path = desktop.join("isra_crash.txt");
        let _ = std::fs::write(
            &log_path,
            format!("ISRA Chatbot Crash Log\n========================\n{}\n", message),
        );
    }
    // Exit the app
    app_handle.exit(1);
}
