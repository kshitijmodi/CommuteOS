/// Base URL for the CommuteOS backend (see backend/ in the repo root).
///
/// Hosted on Render's free tier (`backend/render.yaml`), backed by a free
/// Neon Postgres instance - no more USB/adb reverse tunnel or "run the
/// backend on my laptop" requirement (see OPEN_QUESTIONS.md's now-resolved
/// "Backend hosting/infra" entry for the history/tradeoffs, notably: free
/// tier means the service spins down after ~15min idle and the first
/// request after that takes a bit to wake it back up).
const String apiBaseUrl = 'https://commuteos-backend-wbwk.onrender.com';
