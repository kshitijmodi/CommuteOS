import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Persists the real conversation id Chat AI's server-side memory is
/// keyed on (see backend/app/models/chat_session.py) - minted once
/// on-device and reused across app restarts, so a conversation actually
/// continues rather than resetting every time the app is closed. Works
/// identically for a logged-out caller, same as the rest of this app's
/// "browsing never needs an account" pattern - this is a random client
/// id, not tied to any account.
class ChatSessionStore {
  ChatSessionStore({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  static const _sessionIdKey = 'chat_session_id';

  final Uuid _uuid;

  /// Returns the current session id, minting and persisting a new one on
  /// first use - never regenerated after that unless [startNewSession]
  /// is called, so a follow-up question later in the same install still
  /// has real history to fall back to.
  Future<String> getSessionId() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_sessionIdKey);
    if (existing != null) return existing;

    final fresh = _uuid.v4();
    await prefs.setString(_sessionIdKey, fresh);
    return fresh;
  }

  /// Starts a genuinely new, empty conversation - the next [getSessionId]
  /// call mints a fresh id, so the backend has no prior turns to load for
  /// it. Used by an explicit "New chat" action, not automatically -
  /// nothing should silently drop a real conversation the user didn't
  /// ask to reset.
  Future<void> startNewSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_sessionIdKey);
  }
}
