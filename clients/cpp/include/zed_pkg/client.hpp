#pragma once

#include <cctype>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace zed_pkg {

class Client final {
 public:
  explicit Client(std::string base_url,
                  std::optional<std::string> bearer_token = std::nullopt)
      : base_url_(normalize_base_url(std::move(base_url))),
        bearer_token_(std::move(bearer_token)) {}

  [[nodiscard]] const std::string& base_url() const noexcept {
    return base_url_;
  }

  [[nodiscard]] bool has_bearer_token() const noexcept {
    return bearer_token_.has_value() && !bearer_token_->empty();
  }

  // Request code must opt in to credential access. Generic diagnostics use
  // describe(), which never includes the credential value.
  [[nodiscard]] std::optional<std::string> authorization_header() const {
    if (!has_bearer_token()) {
      return std::nullopt;
    }
    return "Bearer " + *bearer_token_;
  }

  [[nodiscard]] std::string describe() const {
    return "ZedPkgClient(base_url=" + base_url_ + ", token=[REDACTED])";
  }

  [[nodiscard]] static std::string package_path(std::string_view org,
                                                std::string_view name) {
    return "/v1/packages/" + encode_segment(org, "org") + "/" +
           encode_segment(name, "name");
  }

  [[nodiscard]] static std::string version_path(std::string_view org,
                                                std::string_view name,
                                                std::string_view version) {
    return package_path(org, name) + "/versions/" +
           encode_segment(version, "version");
  }

  [[nodiscard]] static std::string artifact_path(std::string_view sha256) {
    if (sha256.size() != 64) {
      throw std::invalid_argument("sha256 must contain exactly 64 hex characters");
    }
    for (const unsigned char byte : sha256) {
      if (!std::isxdigit(byte)) {
        throw std::invalid_argument("sha256 must contain only hex characters");
      }
    }
    return "/v1/artifacts/" + std::string(sha256);
  }

 private:
  static bool is_unreserved(unsigned char byte) noexcept {
    return std::isalnum(byte) || byte == '-' || byte == '.' || byte == '_' ||
           byte == '~';
  }

  static void validate_segment(std::string_view value, std::string_view name) {
    if (value.empty() || value == "." || value == "..") {
      throw std::invalid_argument(std::string(name) + " is not a valid path segment");
    }
    if (value.size() > 256) {
      throw std::invalid_argument(std::string(name) + " exceeds 256 bytes");
    }

    bool has_non_space = false;
    for (const unsigned char byte : value) {
      if (byte < 0x20 || byte == 0x7f) {
        throw std::invalid_argument(std::string(name) + " contains a control character");
      }
      if (!std::isspace(byte)) {
        has_non_space = true;
      }
    }
    if (!has_non_space) {
      throw std::invalid_argument(std::string(name) + " must not be blank");
    }
  }

  static std::string encode_segment(std::string_view value,
                                    std::string_view name) {
    validate_segment(value, name);
    static constexpr char kHex[] = "0123456789ABCDEF";

    std::string encoded;
    encoded.reserve(value.size());
    for (const unsigned char byte : value) {
      if (is_unreserved(byte)) {
        encoded.push_back(static_cast<char>(byte));
      } else {
        encoded.push_back('%');
        encoded.push_back(kHex[(byte >> 4U) & 0x0fU]);
        encoded.push_back(kHex[byte & 0x0fU]);
      }
    }
    return encoded;
  }

  static std::string normalize_base_url(std::string value) {
    constexpr std::string_view kHttp = "http://";
    constexpr std::string_view kHttps = "https://";

    std::size_t authority_start = 0;
    if (value.starts_with(kHttps)) {
      authority_start = kHttps.size();
    } else if (value.starts_with(kHttp)) {
      authority_start = kHttp.size();
    } else {
      throw std::invalid_argument("base_url must use http or https");
    }

    if (value.find('?') != std::string::npos ||
        value.find('#') != std::string::npos ||
        value.find('\\') != std::string::npos) {
      throw std::invalid_argument(
          "base_url must not contain a query, fragment, or backslash");
    }

    for (const unsigned char byte : value) {
      if (std::isspace(byte) || byte < 0x20 || byte == 0x7f) {
        throw std::invalid_argument("base_url must not contain whitespace or control characters");
      }
    }

    const auto authority_end = value.find('/', authority_start);
    const auto authority = value.substr(
        authority_start,
        authority_end == std::string::npos ? std::string::npos
                                           : authority_end - authority_start);
    if (authority.empty() || authority.find('@') != std::string::npos) {
      throw std::invalid_argument(
          "base_url must contain a credential-free authority");
    }

    while (value.size() > authority_start && value.back() == '/') {
      value.pop_back();
    }
    return value;
  }

  std::string base_url_;
  std::optional<std::string> bearer_token_;
};

}  // namespace zed_pkg
