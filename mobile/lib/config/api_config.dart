/// Central place for backend connection settings.
///
/// During development on an Android emulator, `localhost` on the *phone*
/// is not the same machine as your FastAPI server, so 10.0.2.2 is used to
/// reach the host machine. On a real device on the same Wi-Fi as the
/// laptop running the backend, replace this with the laptop's LAN IP
/// (e.g. http://192.168.1.42:8000). In production this becomes the
/// deployed API's HTTPS URL.
class ApiConfig {
  ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'OG_API_BASE_URL',
    defaultValue: 'http://172.16.147.75:8000',
  );

  static const String apiV1 = '$baseUrl/api/v1';

  // How often the app attempts a foreground GPS capture while a fishing
  // trip is active. Real interval tuning (battery vs. trail resolution)
  // is a Stage 2 concern; this is a sane MVP default.
  static const Duration locationCaptureInterval = Duration(minutes: 5);

  static const Duration syncRetryInterval = Duration(seconds: 30);
}
