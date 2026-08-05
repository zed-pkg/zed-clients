#!/usr/bin/env bash
set -euo pipefail

export CI="${CI:-1}"
export NO_COLOR="${NO_COLOR:-1}"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

cache_root="${NIX_AGENT_CACHE_ROOT:-$repo_root/.cache/nix-agent}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$cache_root/xdg}"
export CARGO_HOME="${CARGO_HOME:-$cache_root/cargo}"
export GOPATH="${GOPATH:-$cache_root/go}"
export GOCACHE="${GOCACHE:-$cache_root/go-build}"
export npm_config_cache="${npm_config_cache:-$cache_root/npm}"
export PUB_CACHE="${PUB_CACHE:-$cache_root/dart}"
export REBAR_CACHE_DIR="${REBAR_CACHE_DIR:-$cache_root/rebar3}"
export MIX_HOME="${MIX_HOME:-$cache_root/mix}"
export HEX_HOME="${HEX_HOME:-$cache_root/hex}"
export MAVEN_OPTS="${MAVEN_OPTS:--Dmaven.repo.local=$cache_root/maven}"
mkdir -p \
  "$XDG_CACHE_HOME" \
  "$CARGO_HOME" \
  "$GOPATH" \
  "$GOCACHE" \
  "$npm_config_cache" \
  "$PUB_CACHE" \
  "$REBAR_CACHE_DIR" \
  "$MIX_HOME" \
  "$HEX_HOME" \
  "$cache_root/maven"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'required command is unavailable in the Nix shell: %s\n' "$command_name" >&2
    return 1
  fi
}

require_interfaces_checkout() {
  local interfaces_root="$repo_root/../zed-interfaces"
  if [[ ! -f "$interfaces_root/Cargo.toml" ]]; then
    printf '%s\n' \
      'Rust and WASM checks require zed-pkg/zed-interfaces as a sibling checkout:' \
      "  expected: $interfaces_root/Cargo.toml" >&2
    return 1
  fi
}

run_unlocked_cargo_tests() {
  local had_lock=0
  if [[ -f Cargo.lock ]]; then
    had_lock=1
  fi
  cleanup_generated_lock() {
    if [[ "$had_lock" -eq 0 ]]; then
      rm -f Cargo.lock
    fi
  }
  trap cleanup_generated_lock EXIT
  cargo fmt --check
  cargo test
}

run_stage() {
  local stage="$1"
  printf '\n==> agent-check stage: %s\n' "$stage"

  case "$stage" in
    toolchains)
      local command_name
      for command_name in \
        actionlint cargo dart elixir gleam go java jq mix mvn nix nixfmt node npm \
        php python3 rebar3 ruby rustc rustfmt shellcheck shfmt swift; do
        require_command "$command_name"
      done
      node --version
      npm --version
      python3 --version
      go version
      rustc --version
      cargo --version
      dart --version
      gleam --version
      rebar3 version
      elixir --version
      java -version
      mvn --version
      ruby --version
      php --version
      if [[ -n "${SWIFT_EXEC:-}" ]]; then
        "$SWIFT_EXEC" --version
      else
        swift --version
      fi
      ;;
    preflight)
      git diff --check
      nixfmt --check flake.nix .nix/dev-shell.nix
      shellcheck .nix/agent-check.sh
      shfmt -i 2 -ci -d .nix/agent-check.sh
      actionlint .github/workflows/*.yml
      nix flake check --no-update-lock-file --show-trace
      ;;
    contract)
      python3 scripts/validate-client-matrix.py
      ;;
    typescript)
      (
        cd clients/typescript
        npm ci
        npm run build
        npm test
      )
      ;;
    python)
      (
        cd clients/python
        python3 -m compileall -q zed_pkg_client
        python3 -m unittest -v
      )
      ;;
    go)
      (
        cd clients/go
        gofmt_output="$(gofmt -l .)"
        if [[ -n "$gofmt_output" ]]; then
          printf 'gofmt drift:\n%s\n' "$gofmt_output" >&2
          exit 1
        fi
        go vet ./...
        go test -race ./...
      )
      ;;
    rust)
      require_interfaces_checkout
      (
        cd clients/rust
        run_unlocked_cargo_tests
      )
      ;;
    wasm)
      require_interfaces_checkout
      (
        cd clients/wasm
        run_unlocked_cargo_tests
      )
      ;;
    dart)
      (
        cd clients/dart
        dart pub get
        dart format lib test
        if ! git diff --quiet -- lib test; then
          printf 'Dart formatting drift detected:\n' >&2
          git diff --no-ext-diff -- lib test >&2
          exit 1
        fi
        dart analyze
        dart test
      )
      ;;
    gleam)
      (
        cd clients/gleam
        gleam deps download
        gleam format --check
        gleam test
      )
      ;;
    erlang)
      (
        cd clients/erlang
        rebar3 compile
        rebar3 eunit
      )
      ;;
    elixir)
      (
        cd clients/elixir
        mix deps.get
        mix test
      )
      ;;
    java)
      (
        cd clients/java
        mvn --batch-mode --no-transfer-progress verify
      )
      ;;
    kotlin)
      (
        cd clients/kotlin
        mvn --batch-mode --no-transfer-progress verify
      )
      ;;
    ruby)
      (
        cd clients/ruby
        ruby -c lib/zed_pkg_client.rb
        ruby -Ilib test/client_test.rb
      )
      ;;
    php)
      (
        cd clients/php
        php -l src/Client.php
        php tests/client_test.php
      )
      ;;
    swift)
      (
        cd clients/swift
        if [[ -z "${SWIFT_EXEC:-}" || ! -x "$SWIFT_EXEC" ]]; then
          printf 'SWIFT_EXEC must point to the flake-locked Swift compiler\n' >&2
          exit 1
        fi
        "$SWIFT_EXEC" --version
        swift test --parallel
      )
      ;;
    sdk)
      local sdk_stage
      for sdk_stage in \
        typescript python go rust wasm dart gleam erlang elixir java kotlin ruby php swift; do
        run_stage "$sdk_stage"
      done
      ;;
    all)
      local all_stage
      for all_stage in toolchains preflight contract sdk; do
        run_stage "$all_stage"
      done
      ;;
    *)
      printf 'unknown agent-check stage: %s\n' "$stage" >&2
      return 64
      ;;
  esac
}

case "${1:-all}" in
  all | toolchains | preflight | contract | sdk | typescript | python | go | rust | wasm | dart | gleam | erlang | elixir | java | kotlin | ruby | php | swift)
    run_stage "${1:-all}"
    ;;
  *)
    printf '%s\n' \
      'usage: agent-check [all|toolchains|preflight|contract|sdk|typescript|python|go|rust|wasm|dart|gleam|erlang|elixir|java|kotlin|ruby|php|swift]' >&2
    exit 64
    ;;
esac
