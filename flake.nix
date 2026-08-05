{
  description = "Agent-first development environment for the zed-pkg client SDK matrix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs, ... }:
    let
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];
      stages = [
        "toolchains"
        "preflight"
        "contract"
        "typescript"
        "python"
        "go"
        "rust"
        "wasm"
        "dart"
        "gleam"
        "erlang"
        "java"
        "swift"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };

      swiftRuntimeFor =
        pkgs:
        pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
          pkgs.swiftPackages.Dispatch
          pkgs.swiftPackages.Foundation
          pkgs.swiftPackages.XCTest
        ];

      swiftLibraryPathFor = pkgs: pkgs.lib.makeLibraryPath (swiftRuntimeFor pkgs);

      swiftToolchainFor =
        pkgs:
        let
          upstream = pkgs.swiftPackages.swift-unwrapped;
          swiftUnwrapped = pkgs.runCommand "zed-swift-unwrapped-${upstream.version}" {
            outputs = [
              "out"
              "lib"
              "dev"
              "doc"
              "man"
            ];
            inherit (upstream) version;
            passthru = upstream.passthru or { };
            meta = upstream.meta or { };
          } ''
            mirror_output() {
              source="$1"
              destination="$2"
              mkdir -p "$destination"
              cp -rs "$source"/. "$destination"/
            }

            mirror_output ${upstream} "$out"
            mirror_output ${upstream.lib} "$lib"
            mirror_output ${upstream.dev} "$dev"
            mirror_output ${upstream.doc} "$doc"
            mirror_output ${upstream.man} "$man"

            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              # SwiftPM records the compiler's separate `lib` output when it is
              # built. Nixpkgs stores libIndexStore in `out`, so add only the
              # missing immutable path without rebuilding the compiler.
              mkdir -p "$lib/lib"
              ln -s ${upstream}/lib/libIndexStore.so "$lib/lib/libIndexStore.so"
            ''}
          '';
          swift = pkgs.swiftPackages.swift.override {
            swift = swiftUnwrapped;
          };
          swiftpm = pkgs.swiftPackages.swiftpm.override {
            inherit swift;
          };
        in
        {
          inherit swift swiftpm swiftUnwrapped;
        };

      commonToolchainFor =
        pkgs:
        with pkgs;
        [
          bash
          cacert
          coreutils
          findutils
          gawk
          git
          gnugrep
          gnused
          gzip
          jq
          unzip
        ];

      stageToolchainFor =
        pkgs: stage:
        let
          node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
          python = pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs;
          erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
          swiftToolchain = swiftToolchainFor pkgs;
          focused =
            if stage == "toolchains" then
              with pkgs;
              [
                actionlint
                cargo
                dart
                gleam
                go
                jdk17
                maven
                nix
                nixfmt
                node
                python
                rebar3
                rustc
                rustfmt
                shellcheck
                shfmt
                wasm-pack
                erlang
                swiftPackages.swift
                swiftPackages.swiftpm
              ]
            else if stage == "preflight" then
              with pkgs;
              [
                actionlint
                nix
                nixfmt
                shellcheck
                shfmt
              ]
            else if stage == "contract" then
              [ python ]
            else if stage == "typescript" then
              [ node ]
            else if stage == "python" then
              [ python ]
            else if stage == "go" then
              [ pkgs.go ]
            else if stage == "rust" then
              with pkgs;
              [
                cargo
                gcc
                openssl
                pkg-config
                rustc
                rustfmt
              ]
            else if stage == "wasm" then
              with pkgs;
              [
                cargo
                gcc
                pkg-config
                rustc
                rustfmt
                wasm-pack
              ]
            else if stage == "dart" then
              [ pkgs.dart ]
            else if stage == "gleam" then
              [
                pkgs.gleam
                erlang
                pkgs.rebar3
              ]
            else if stage == "erlang" then
              [
                erlang
                pkgs.rebar3
              ]
            else if stage == "java" then
              [
                pkgs.jdk17
                pkgs.maven
              ]
            else if stage == "swift" then
              [
                swiftToolchain.swift
                swiftToolchain.swiftpm
              ]
            else
              throw "unknown zed-clients agent-check stage: ${stage}";
        in
        pkgs.lib.unique (commonToolchainFor pkgs ++ focused);

      fullToolchainFor =
        pkgs:
        let
          node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
          python = pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs;
          erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
          swiftToolchain = swiftToolchainFor pkgs;
        in
        pkgs.lib.unique (
          commonToolchainFor pkgs
          ++ (with pkgs; [
            actionlint
            cargo
            curl
            dart
            gcc
            gleam
            go
            jdk17
            maven
            nix
            nixfmt
            node
            openssl
            pkg-config
            python
            rebar3
            rustc
            rustfmt
            shellcheck
            shfmt
            wasm-pack
          ])
          ++ [
            erlang
            swiftToolchain.swift
            swiftToolchain.swiftpm
          ]
        );
    in
    {
      formatter = forAllSystems (system: (pkgsFor system).nixfmt);

      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          agentCheck = pkgs.writeShellApplication {
            name = "agent-check";
            runtimeInputs = [ pkgs.bash ];
            text = builtins.readFile ./.nix/agent-check.sh;
          };
        in
        {
          inherit agentCheck;
          default = agentCheck;
        }
      );

      apps = forAllSystems (system: {
        agent-check = {
          type = "app";
          program = "${self.packages.${system}.agentCheck}/bin/agent-check";
        };
        default = self.apps.${system}.agent-check;
      });

      checks = forAllSystems (system: {
        agentCheck = self.packages.${system}.agentCheck;
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          agentCheck = self.packages.${system}.agentCheck;
          swiftToolchain = swiftToolchainFor pkgs;
          focusedShells = pkgs.lib.genAttrs stages (
            stage:
            let
              isSwift = stage == "swift";
            in
            import ./.nix/dev-shell.nix {
              inherit pkgs agentCheck;
              toolchain = stageToolchainFor pkgs stage;
              swiftRuntime = if isSwift then swiftRuntimeFor pkgs else [ ];
              swiftCompiler = if isSwift then swiftToolchain.swift else null;
              swiftLibraryPath = if isSwift then swiftLibraryPathFor pkgs else "";
            }
          );
        in
        focusedShells
        // {
          default = import ./.nix/dev-shell.nix {
            inherit pkgs agentCheck;
            toolchain = fullToolchainFor pkgs;
            swiftRuntime = swiftRuntimeFor pkgs;
            swiftCompiler = swiftToolchain.swift;
            swiftLibraryPath = swiftLibraryPathFor pkgs;
          };
        }
      );
    };
}
