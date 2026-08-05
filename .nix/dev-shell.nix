{
  pkgs,
  agentCheck,
  toolchain,
  swiftCompiler ? null,
  swiftLibraryPath ? "",
  swiftRuntime ? [ ],
}:
let
  swiftEnvironment = pkgs.lib.optionalString (swiftCompiler != null) ''
    export SWIFT_EXEC="${swiftCompiler}/bin/swiftc"
    export LD_LIBRARY_PATH="${swiftLibraryPath}:''${LD_LIBRARY_PATH:-}"
  '';
in
pkgs.mkShell {
  packages = toolchain ++ [ agentCheck ];

  # Swift's wrapped compiler discovers Foundation, Dispatch, and XCTest module
  # search paths from buildInputs. Non-Swift focused shells keep this empty.
  buildInputs = swiftRuntime;

  LANG = if pkgs.stdenv.hostPlatform.isDarwin then "en_US.UTF-8" else "C.UTF-8";
  LC_ALL = if pkgs.stdenv.hostPlatform.isDarwin then "en_US.UTF-8" else "C.UTF-8";

  shellHook = ''
    export NIX_DEV_SHELL=zed-clients
    ${swiftEnvironment}
    export NIX_AGENT_CACHE_ROOT="''${NIX_AGENT_CACHE_ROOT:-$PWD/.cache/nix-agent}"
    export XDG_CACHE_HOME="''${XDG_CACHE_HOME:-$NIX_AGENT_CACHE_ROOT/xdg}"
    export CARGO_HOME="''${CARGO_HOME:-$NIX_AGENT_CACHE_ROOT/cargo}"
    export GOPATH="''${GOPATH:-$NIX_AGENT_CACHE_ROOT/go}"
    export GOCACHE="''${GOCACHE:-$NIX_AGENT_CACHE_ROOT/go-build}"
    export npm_config_cache="''${npm_config_cache:-$NIX_AGENT_CACHE_ROOT/npm}"
    export PUB_CACHE="''${PUB_CACHE:-$NIX_AGENT_CACHE_ROOT/dart}"
    export REBAR_CACHE_DIR="''${REBAR_CACHE_DIR:-$NIX_AGENT_CACHE_ROOT/rebar3}"
    export MAVEN_OPTS="''${MAVEN_OPTS:--Dmaven.repo.local=$NIX_AGENT_CACHE_ROOT/maven}"
    mkdir -p \
      "$XDG_CACHE_HOME" \
      "$CARGO_HOME" \
      "$GOPATH" \
      "$GOCACHE" \
      "$npm_config_cache" \
      "$PUB_CACHE" \
      "$REBAR_CACHE_DIR" \
      "$NIX_AGENT_CACHE_ROOT/maven"
  '';
}
