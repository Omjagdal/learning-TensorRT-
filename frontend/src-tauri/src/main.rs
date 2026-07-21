// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

/// Global handle to the backend process so we can kill it on exit.
static BACKEND_PROCESS: Mutex<Option<Child>> = Mutex::new(None);

/// Read the port number from the temp file written by the Python backend.
fn read_port_file() -> Option<u16> {
    let temp_dir = env::temp_dir();
    let port_file = temp_dir.join("isra_port.txt");

    if let Ok(content) = fs::read_to_string(&port_file) {
        content.trim().parse::<u16>().ok()
    } else {
        None
    }
}

/// Check if the backend is ready by hitting the health endpoint.
fn check_backend_health(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{}/api/v1/health", port);
    match reqwest::blocking::get(&url) {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

/// Find the backend executable path.
/// In production: looks in the same directory as the Tauri exe.
/// In dev: looks in backend/dist/IsraChatbot/.
fn find_backend_exe() -> Option<PathBuf> {
    // Production: alongside the Tauri executable
    if let Ok(exe_path) = env::current_exe() {
        let exe_dir = exe_path.parent().unwrap_or_else(|| std::path::Path::new("."));

        // Check: binaries/IsraChatbot/IsraChatbot.exe (MSI layout)
        let candidate = exe_dir
            .join("binaries")
            .join("IsraChatbot")
            .join("IsraChatbot.exe");
        if candidate.exists() {
            return Some(candidate);
        }

        // Check: same directory
        let candidate = exe_dir.join("IsraChatbot.exe");
        if candidate.exists() {
            return Some(candidate);
        }
    }

    // Dev fallback: relative to project root
    let dev_path = PathBuf::from("../backend/dist/IsraChatbot/IsraChatbot.exe");
    if dev_path.exists() {
        return Some(dev_path);
    }

    None
}

fn main() {
    // 1. Find and spawn the backend executable
    let backend_exe = find_backend_exe();

    if let Some(exe_path) = backend_exe {
        println!("Starting backend: {:?}", exe_path);

        #[cfg(target_os = "windows")]
        let child = {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            Command::new(&exe_path)
                .creation_flags(CREATE_NO_WINDOW)
                .spawn()
        };

        #[cfg(not(target_os = "windows"))]
        let child = Command::new(&exe_path).spawn();

        match child {
            Ok(process) => {
                let mut guard = BACKEND_PROCESS.lock().unwrap();
                *guard = Some(process);
                println!("Backend process started.");
            }
            Err(e) => {
                eprintln!("Failed to start backend: {}", e);
            }
        }
    } else {
        eprintln!("WARNING: Backend executable not found. The app may not work.");
    }

    // 2. Wait for the backend to write its port file and become healthy
    let mut port: Option<u16> = None;
    let max_wait = 60; // seconds

    for i in 0..max_wait * 2 {
        if let Some(p) = read_port_file() {
            if check_backend_health(p) {
                port = Some(p);
                println!("Backend ready on port {}", p);
                break;
            }
        }
        if i % 10 == 0 {
            println!("Waiting for backend... ({}/{}s)", i / 2, max_wait);
        }
        thread::sleep(Duration::from_millis(500));
    }

    let backend_url = match port {
        Some(p) => format!("http://127.0.0.1:{}", p),
        None => {
            eprintln!("ERROR: Backend did not start within {}s", max_wait);
            // Still try the default port as last resort
            "http://127.0.0.1:8000".to_string()
        }
    };

    // 3. Build and run the Tauri application
    tauri::Builder::default()
        .setup(move |app| {
            // Navigate the main window to the backend URL
            if let Some(window) = app.get_webview_window("main") {
                let url: tauri::Url = backend_url.parse().expect("Invalid backend URL");
                let _ = window.navigate(url);

                // Make window visible after navigating
                let window_clone = window.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(Duration::from_millis(500));
                    let _ = window_clone.show();
                });
            }
            Ok(())
        })
        .on_window_event(|_window, event| {
            // Kill backend when the window is destroyed
            if let tauri::WindowEvent::Destroyed = event {
                let mut guard = BACKEND_PROCESS.lock().unwrap();
                if let Some(ref mut child) = *guard {
                    println!("Shutting down backend process...");
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running ISRA Chatbot");
}
