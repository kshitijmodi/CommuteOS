import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import 'chat_repository.dart';

class _Message {
  const _Message({required this.text, required this.isUser, this.isError = false});

  final String text;
  final bool isUser;
  final bool isError;
}

/// Chat AI (see backend/app/chat_ai.py) - free-text questions about
/// real-time transit, no account required. Real conversation memory
/// (added 2026-08-08): the same persistent session id is sent with every
/// question (see ChatRepository), so a follow-up like "what about the
/// other direction" is resolved against what was actually said earlier -
/// the "New chat" action in the app bar starts a genuinely fresh session
/// when the user wants a clean slate.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.chatRepository});

  final ChatRepository? chatRepository;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final _chatRepository = widget.chatRepository ?? ChatRepository();
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  final _messages = <_Message>[];
  bool _isSending = false;

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final question = _inputController.text.trim();
    if (question.isEmpty || _isSending) return;

    setState(() {
      _messages.add(_Message(text: question, isUser: true));
      _isSending = true;
    });
    _inputController.clear();
    _scrollToBottom();

    try {
      final answer = await _chatRepository.ask(question);
      setState(() {
        _messages.add(_Message(text: answer.text, isUser: false));
      });
    } on ChatException catch (e) {
      setState(() {
        _messages.add(_Message(text: e.message, isUser: false, isError: true));
      });
    } catch (e) {
      setState(() {
        _messages.add(
          _Message(
            text: 'Could not reach the chat assistant. Try again later.',
            isUser: false,
            isError: true,
          ),
        );
      });
    } finally {
      if (mounted) setState(() => _isSending = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _startNewChat() async {
    await _chatRepository.startNewConversation();
    setState(() => _messages.clear());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ask CommuteOS'),
        actions: [
          if (_messages.isNotEmpty)
            IconButton(
              onPressed: _isSending ? null : _startNewChat,
              icon: const Icon(Icons.add_comment_outlined),
              tooltip: 'New chat',
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? const _ChatEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(AppSpacing.md),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) =>
                        _MessageBubble(message: _messages[index]),
                  ),
          ),
          if (_isSending)
            const Padding(
              padding: EdgeInsets.only(bottom: AppSpacing.sm),
              child: _TypingIndicator(),
            ),
          _ChatInputBar(
            controller: _inputController,
            enabled: !_isSending,
            onSend: _send,
          ),
        ],
      ),
    );
  }
}

class _ChatEmptyState extends StatelessWidget {
  const _ChatEmptyState();

  @override
  Widget build(BuildContext context) {
    return const EmptyState(
      icon: Icons.chat_bubble_outline_rounded,
      title: 'Ask about any station',
      message:
          'Try "what time\'s the next PATH train from Grove Street" or '
          '"when\'s the next train at Hoboken". No account needed.',
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final _Message message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final color = isUser
        ? AppColors.accent
        : message.isError
        ? AppColors.error.withValues(alpha: 0.14)
        : AppColors.surfaceRaised;
    final textColor = isUser
        ? const Color(0xFF00201A)
        : message.isError
        ? AppColors.error
        : AppColors.textPrimary;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: AppSpacing.sm),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 10,
        ),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(AppRadius.lg),
        ),
        child: Text(message.text, style: TextStyle(color: textColor, height: 1.3)),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return const Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: AppColors.accent,
          ),
        ),
      ),
    );
  }
}

class _ChatInputBar extends StatelessWidget {
  const _ChatInputBar({
    required this.controller,
    required this.enabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool enabled;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.sm,
          AppSpacing.md,
          AppSpacing.sm,
        ),
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppColors.border)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                enabled: enabled,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                decoration: const InputDecoration(
                  hintText: 'Ask about a station or arrival time…',
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            IconButton.filled(
              onPressed: enabled ? onSend : null,
              icon: const Icon(Icons.arrow_upward_rounded),
            ),
          ],
        ),
      ),
    );
  }
}
