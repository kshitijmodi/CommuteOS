import 'package:flutter/material.dart';

import 'auth_repository.dart';
import 'preferences_screen.dart';
import 'recommendation_screen.dart';

/// Optional account screen - browsing/favoriting never requires this.
/// Signing in here is what turns on trip logging (see TripLogger), which
/// feeds Phase 2's learned-preferences model.
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _authRepository = AuthRepository();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  late Future<bool> _isLoggedInFuture;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _isLoggedInFuture = _authRepository.isLoggedIn();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _refreshLoginState() {
    setState(() => _isLoggedInFuture = _authRepository.isLoggedIn());
  }

  Future<void> _submit({required bool isSignup}) async {
    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      if (isSignup) {
        await _authRepository.signup(
          _emailController.text.trim(),
          _passwordController.text,
        );
      } else {
        await _authRepository.login(
          _emailController.text.trim(),
          _passwordController.text,
        );
      }
      _refreshLoginState();
    } on AuthException catch (e) {
      setState(() => _errorMessage = e.message);
    } catch (e) {
      setState(
        () => _errorMessage = 'Could not reach the server. Try again later.',
      );
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  Future<void> _logout() async {
    await _authRepository.logout();
    _refreshLoginState();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: FutureBuilder<bool>(
        future: _isLoggedInFuture,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.data == true) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle, size: 48, color: Colors.green),
                    const SizedBox(height: 16),
                    const Text('You are signed in.'),
                    const SizedBox(height: 8),
                    const Text(
                      'CommuteOS is now logging the stations you check to '
                      'learn your commute over time.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const PreferencesScreen(),
                        ),
                      ),
                      icon: const Icon(Icons.insights),
                      label: const Text('What CommuteOS has learned'),
                    ),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const RecommendationScreen(),
                        ),
                      ),
                      icon: const Icon(Icons.alt_route),
                      label: const Text('What should I take?'),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: _logout,
                      child: const Text('Log out'),
                    ),
                  ],
                ),
              ),
            );
          }

          return Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text(
                  'Signing in lets CommuteOS learn your commute over time. '
                  'Browsing and favorites always work without an account.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                TextField(
                  controller: _emailController,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _passwordController,
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    border: OutlineInputBorder(),
                  ),
                  obscureText: true,
                ),
                if (_errorMessage != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _errorMessage!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _isSubmitting
                            ? null
                            : () => _submit(isSignup: false),
                        child: const Text('Log in'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: _isSubmitting
                            ? null
                            : () => _submit(isSignup: true),
                        child: const Text('Sign up'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
