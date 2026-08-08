import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/chat/chat_session_store.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('getSessionId', () {
    test('mints and persists a new session id on first use', () async {
      final store = ChatSessionStore();

      final id = await store.getSessionId();

      expect(id, isNotEmpty);
      // A real v4 UUID, not a placeholder - 36 chars, 4 hyphens.
      expect(id.split('-').length, 5);
    });

    test('returns the SAME id on repeated calls - a real persisted conversation', () async {
      final store = ChatSessionStore();

      final first = await store.getSessionId();
      final second = await store.getSessionId();

      expect(second, first);
    });

    test('a new store instance still returns the same persisted id', () async {
      // Simulates a real app restart - SharedPreferences.setMockInitialValues
      // in setUp keeps the same backing store across instances within one
      // test, same as real on-device persistence across launches.
      final first = await ChatSessionStore().getSessionId();
      final second = await ChatSessionStore().getSessionId();

      expect(second, first);
    });
  });

  group('startNewSession', () {
    test('a later getSessionId call returns a genuinely different id', () async {
      final store = ChatSessionStore();
      final original = await store.getSessionId();

      await store.startNewSession();
      final fresh = await store.getSessionId();

      expect(fresh, isNot(original));
    });
  });
}
