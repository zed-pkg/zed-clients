const std = @import("std");

pub const ClientError = error{
    InvalidBaseUrl,
    InvalidSegment,
    InvalidDigest,
};

pub const Client = struct {
    base_url: []const u8,
    bearer_token: ?[]const u8 = null,

    pub fn init(base_url: []const u8, bearer_token: ?[]const u8) ClientError!Client {
        try validateBaseUrl(base_url);
        return .{
            .base_url = trimTrailingSlashes(base_url),
            .bearer_token = bearer_token,
        };
    }

    pub fn hasBearerToken(self: Client) bool {
        return if (self.bearer_token) |token| token.len > 0 else false;
    }

    // Request code must opt in to credential access. Generic diagnostics use
    // description(), which never includes the credential value.
    pub fn authorizationHeader(self: Client, allocator: std.mem.Allocator) !?[]u8 {
        const token = self.bearer_token orelse return null;
        if (token.len == 0) return null;
        return try std.fmt.allocPrint(allocator, "Bearer {s}", .{token});
    }

    pub fn description(self: Client, allocator: std.mem.Allocator) ![]u8 {
        return std.fmt.allocPrint(
            allocator,
            "ZedPkgClient(base_url={s}, token=[REDACTED])",
            .{self.base_url},
        );
    }

    pub fn packagePath(
        allocator: std.mem.Allocator,
        org: []const u8,
        name: []const u8,
    ) ![]u8 {
        const encoded_org = try encodeSegment(allocator, org);
        defer allocator.free(encoded_org);
        const encoded_name = try encodeSegment(allocator, name);
        defer allocator.free(encoded_name);
        return std.fmt.allocPrint(
            allocator,
            "/v1/packages/{s}/{s}",
            .{ encoded_org, encoded_name },
        );
    }

    pub fn versionPath(
        allocator: std.mem.Allocator,
        org: []const u8,
        name: []const u8,
        version: []const u8,
    ) ![]u8 {
        const package_path = try packagePath(allocator, org, name);
        defer allocator.free(package_path);
        const encoded_version = try encodeSegment(allocator, version);
        defer allocator.free(encoded_version);
        return std.fmt.allocPrint(
            allocator,
            "{s}/versions/{s}",
            .{ package_path, encoded_version },
        );
    }

    pub fn artifactPath(
        allocator: std.mem.Allocator,
        sha256: []const u8,
    ) ![]u8 {
        if (sha256.len != 64) return error.InvalidDigest;
        for (sha256) |byte| {
            if (!isHex(byte)) return error.InvalidDigest;
        }
        return std.fmt.allocPrint(allocator, "/v1/artifacts/{s}", .{sha256});
    }
};

fn validateBaseUrl(base_url: []const u8) ClientError!void {
    const https_prefix = "https://";
    const http_prefix = "http://";
    const authority_start = if (std.mem.startsWith(u8, base_url, https_prefix))
        https_prefix.len
    else if (std.mem.startsWith(u8, base_url, http_prefix))
        http_prefix.len
    else
        return error.InvalidBaseUrl;

    if (std.mem.indexOfScalar(u8, base_url, '?') != null or
        std.mem.indexOfScalar(u8, base_url, '#') != null or
        std.mem.indexOfScalar(u8, base_url, '\\') != null)
    {
        return error.InvalidBaseUrl;
    }

    for (base_url) |byte| {
        if (isWhitespace(byte) or byte < 0x20 or byte == 0x7f) {
            return error.InvalidBaseUrl;
        }
    }

    const remainder = base_url[authority_start..];
    const authority_end = std.mem.indexOfScalar(u8, remainder, '/') orelse remainder.len;
    const authority = remainder[0..authority_end];
    if (authority.len == 0 or std.mem.indexOfScalar(u8, authority, '@') != null) {
        return error.InvalidBaseUrl;
    }
}

fn trimTrailingSlashes(value: []const u8) []const u8 {
    var end = value.len;
    while (end > 0 and value[end - 1] == '/') : (end -= 1) {}
    return value[0..end];
}

fn validateSegment(value: []const u8) ClientError!void {
    if (value.len == 0 or value.len > 256 or
        std.mem.eql(u8, value, ".") or std.mem.eql(u8, value, ".."))
    {
        return error.InvalidSegment;
    }

    var has_non_space = false;
    for (value) |byte| {
        if (byte < 0x20 or byte == 0x7f) return error.InvalidSegment;
        if (!isWhitespace(byte)) has_non_space = true;
    }
    if (!has_non_space) return error.InvalidSegment;
}

fn encodeSegment(allocator: std.mem.Allocator, value: []const u8) ![]u8 {
    try validateSegment(value);

    var encoded_length: usize = 0;
    for (value) |byte| {
        encoded_length += if (isUnreserved(byte)) 1 else 3;
    }

    const encoded = try allocator.alloc(u8, encoded_length);
    errdefer allocator.free(encoded);
    const hex = "0123456789ABCDEF";
    var cursor: usize = 0;
    for (value) |byte| {
        if (isUnreserved(byte)) {
            encoded[cursor] = byte;
            cursor += 1;
        } else {
            const high: usize = @intCast(byte >> 4);
            const low: usize = @intCast(byte & 0x0f);
            encoded[cursor] = '%';
            encoded[cursor + 1] = hex[high];
            encoded[cursor + 2] = hex[low];
            cursor += 3;
        }
    }
    return encoded;
}

fn isUnreserved(byte: u8) bool {
    return (byte >= 'a' and byte <= 'z') or
        (byte >= 'A' and byte <= 'Z') or
        (byte >= '0' and byte <= '9') or
        byte == '-' or byte == '.' or byte == '_' or byte == '~';
}

fn isHex(byte: u8) bool {
    return (byte >= '0' and byte <= '9') or
        (byte >= 'a' and byte <= 'f') or
        (byte >= 'A' and byte <= 'F');
}

fn isWhitespace(byte: u8) bool {
    return byte == ' ' or byte == '\t' or byte == '\n' or byte == '\r' or
        byte == 0x0b or byte == 0x0c;
}

test "client validates registry URLs and redacts diagnostics" {
    const secret = "den-3450-zig-test-token";
    const client = try Client.init("https://registry.zpkg.tech/api/", secret);

    try std.testing.expectEqualStrings("https://registry.zpkg.tech/api", client.base_url);
    try std.testing.expect(client.hasBearerToken());

    const header = (try client.authorizationHeader(std.testing.allocator)).?;
    defer std.testing.allocator.free(header);
    try std.testing.expectEqualStrings("Bearer " ++ secret, header);

    const rendered = try client.description(std.testing.allocator);
    defer std.testing.allocator.free(rendered);
    try std.testing.expect(std.mem.indexOf(u8, rendered, secret) == null);
    try std.testing.expect(std.mem.indexOf(u8, rendered, "[REDACTED]") != null);

    try std.testing.expectError(
        error.InvalidBaseUrl,
        Client.init("https://user:pass@registry.zpkg.tech", null),
    );
    try std.testing.expectError(
        error.InvalidBaseUrl,
        Client.init("https://registry.zpkg.tech?token=secret", null),
    );
    try std.testing.expectError(
        error.InvalidBaseUrl,
        Client.init("file:///tmp/registry", null),
    );
}

test "client builds canonical package and artifact paths" {
    const package_path = try Client.packagePath(
        std.testing.allocator,
        "acme",
        "hello world",
    );
    defer std.testing.allocator.free(package_path);
    try std.testing.expectEqualStrings(
        "/v1/packages/acme/hello%20world",
        package_path,
    );

    const version_path = try Client.versionPath(
        std.testing.allocator,
        "acme",
        "widget",
        "1.2.3",
    );
    defer std.testing.allocator.free(version_path);
    try std.testing.expectEqualStrings(
        "/v1/packages/acme/widget/versions/1.2.3",
        version_path,
    );

    const digest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const artifact_path = try Client.artifactPath(std.testing.allocator, digest);
    defer std.testing.allocator.free(artifact_path);
    try std.testing.expectEqualStrings(
        "/v1/artifacts/" ++ digest,
        artifact_path,
    );

    try std.testing.expectError(
        error.InvalidSegment,
        Client.packagePath(std.testing.allocator, ".", "widget"),
    );
    try std.testing.expectError(
        error.InvalidDigest,
        Client.artifactPath(std.testing.allocator, "not-a-digest"),
    );
}
