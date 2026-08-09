final class ZedClient {
  const ZedClient({required this.baseUrl, this.bearerToken});
  final Uri baseUrl;
  final String? bearerToken;
}
