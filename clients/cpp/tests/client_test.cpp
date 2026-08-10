#include "zed_pkg/client.hpp"

#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {

void expect(bool condition, std::string_view message) {
  if (!condition) {
    throw std::runtime_error(std::string(message));
  }
}

void expect_invalid(const std::function<void()>& operation,
                    std::string_view message) {
  try {
    operation();
  } catch (const std::invalid_argument&) {
    return;
  }
  throw std::runtime_error(std::string(message));
}

}  // namespace

int main() {
  try {
    const std::string secret = "den-3450-cpp-test-token";
    const zed_pkg::Client client("https://registry.zpkg.tech/api/", secret);

    expect(client.base_url() == "https://registry.zpkg.tech/api",
           "base URL should be normalized without a trailing slash");
    expect(client.has_bearer_token(), "client should retain an explicit token");
    expect(client.authorization_header() == "Bearer " + secret,
           "request code should receive the explicit authorization header");

    const auto description = client.describe();
    expect(description.find(secret) == std::string::npos,
           "diagnostics must not contain the bearer token");
    expect(description.find("[REDACTED]") != std::string::npos,
           "diagnostics should make redaction explicit");

    expect(zed_pkg::Client::package_path("acme", "hello world") ==
               "/v1/packages/acme/hello%20world",
           "package coordinates should be encoded as path segments");
    expect(zed_pkg::Client::version_path("acme", "widget", "1.2.3") ==
               "/v1/packages/acme/widget/versions/1.2.3",
           "version paths should preserve valid unreserved characters");
    expect(zed_pkg::Client::artifact_path(std::string(64, 'a')) ==
               "/v1/artifacts/" + std::string(64, 'a'),
           "artifact paths should require a canonical SHA-256 string");

    expect_invalid(
        [] { zed_pkg::Client("https://user:pass@registry.zpkg.tech"); },
        "credential-bearing registry URLs must be rejected");
    expect_invalid(
        [] { zed_pkg::Client("https://registry.zpkg.tech?token=secret"); },
        "query-bearing registry URLs must be rejected");
    expect_invalid([] { zed_pkg::Client("file:///tmp/registry"); },
                   "non-HTTP registry URLs must be rejected");
    expect_invalid([] { (void)zed_pkg::Client::package_path(".", "widget"); },
                   "dot path segments must be rejected");
    expect_invalid([] { (void)zed_pkg::Client::artifact_path("not-a-digest"); },
                   "invalid artifact digests must be rejected");
  } catch (const std::exception& error) {
    std::cerr << "C++ client contract failed: " << error.what() << '\n';
    return 1;
  }

  std::cout << "C++ client contract passed\n";
  return 0;
}
