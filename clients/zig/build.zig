const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});

    const client_module = b.addModule("zed_pkg_client", .{
        .root_source_file = b.path("src/client.zig"),
        .target = target,
    });

    const client_tests = b.addTest(.{
        .root_module = client_module,
    });
    const run_client_tests = b.addRunArtifact(client_tests);

    const test_step = b.step("test", "Run dependency-free Zig client tests");
    test_step.dependOn(&run_client_tests.step);
}
