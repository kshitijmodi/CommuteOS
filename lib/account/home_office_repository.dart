import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

class HomeOffice {
  const HomeOffice({
    required this.homeStation,
    required this.officeStation,
    required this.confirmed,
    required this.homeMode,
    required this.officeMode,
  });

  final String? homeStation;
  final String? officeStation;
  final bool confirmed;
  // Which agency each station code belongs to (e.g. "path", "mta") - a
  // bare code alone is ambiguous across agencies. Added 2026-08-12 so
  // StationGeofenceService can resolve these to real stations (with real
  // lat/lng) without guessing which agency's data to search.
  final String? homeMode;
  final String? officeMode;

  bool get hasInference => homeStation != null || officeStation != null;

  factory HomeOffice.fromJson(Map<String, dynamic> json) {
    return HomeOffice(
      homeStation: json['home_station'] as String?,
      officeStation: json['office_station'] as String?,
      confirmed: json['confirmed'] as bool,
      homeMode: json['home_mode'] as String?,
      officeMode: json['office_mode'] as String?,
    );
  }
}

/// Home/office station inference (Phase 2) - "confirmed once via a simple
/// prompt" per the PRD; see HomeOfficeConfirmationBanner for that prompt.
class HomeOfficeRepository {
  HomeOfficeRepository({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  Future<HomeOffice?> getMyHomeOffice() async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.get(
      Uri.parse('$apiBaseUrl/home-office/me'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) return null;

    return HomeOffice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<HomeOffice?> inferMyHomeOffice() async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/home-office/me/infer'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) return null;

    return HomeOffice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<HomeOffice?> confirmMyHomeOffice() async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/home-office/me/confirm'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) return null;

    return HomeOffice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}
