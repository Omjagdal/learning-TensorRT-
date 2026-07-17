// src-tauri/src/lib.rs
// Required by Tauri 2.x for the library entry point

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // This is intentionally empty — main() in main.rs handles everything.
    // lib.rs is required by Tauri 2.x build system.
}
