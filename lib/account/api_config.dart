/// Base URL for the CommuteOS backend (see backend/ in the repo root).
///
/// Uses "localhost" via `adb reverse tcp:8001 tcp:8001` - the phone's own
/// localhost:8001 tunnels over the USB cable to the dev laptop's real
/// localhost:8001. This was switched from the laptop's Wi-Fi IP after
/// discovering this dev machine's firewall/managed security software
/// blocks inbound network connections to the backend even with an
/// explicit allow rule (see OPEN_QUESTIONS.md) - USB sidesteps that
/// entirely and is also more reliable (doesn't break if the laptop's IP
/// changes). Requires running `adb reverse tcp:8001 tcp:8001` once per
/// USB connection/session before the app can reach the backend.
///
/// Port 8001, not FastAPI's usual 8000 default: this dev machine already
/// runs an unrelated project on 8000, discovered the hard way when this
/// app's requests were silently hitting that other server instead. Start
/// the backend with `uvicorn app.main:app --port 8001`.
///
/// This will need to change to a real hosted URL once the backend has
/// somewhere to live outside local dev (see OPEN_QUESTIONS.md -
/// "Backend hosting/infra" is still unresolved).
const String apiBaseUrl = 'http://localhost:8001';
