/// Base URL for the CommuteOS backend (see backend/ in the repo root).
///
/// Points at the dev machine's local network IP so a phone on the same
/// Wi-Fi can reach it - "localhost" from the phone would mean the phone
/// itself, not the laptop running the backend. This will need to change
/// to a real hosted URL once the backend has somewhere to live outside
/// local dev (see OPEN_QUESTIONS.md - "Backend hosting/infra" is still
/// unresolved).
const String apiBaseUrl = 'http://192.168.1.19:8000';
