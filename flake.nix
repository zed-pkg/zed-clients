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
        "c"
        "cpp"
        "zig"
        "typescript"
        "python"
        "go"
        "rust"
        "wasm"
        "dart"
        "gleam"
        "erlang"
        "elixir"
        "java"
        "kotlin"
        "ruby"
        "php"
        "swift"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };

      runtimePackagesFor = pkgs: {
        node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
        python = (pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs).withPackages (
          pythonPackages: with pythonPackages; [
            jsonschema
            tomlkit
          ]
        );
        erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
        elixir = pkgs.lib.attrByPath [ "beam27Packages" "elixir_1_17" ] pkgs.elixir pkgs;
        swift = pkgs.swiftPackages.swift;
        swiftpm = pkgs.swiftPackages.swiftpm;
        swiftRuntime =
          if pkgs.stdenv.hostPlatform.isDarwin then
            [ ]
          else
            [
              pkgs.swiftPackages.Dispatch
              pkgs.swiftPackages.Foundation
            ];
      };

      commonToolchainFor =
        pkgs: with pkgs; [
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
          runtime = runtimePackagesFor pkgs;
          focused =
            if stage == "toolchains" then
              (with pkgs; [
                actionlint
                cargo
                cmake
                dart
                gleam
                go
                jdk17
                maven
                nix
                nixfmt
                rebar3
                ruby
                php
                rustc
                rustfmt
                shellcheck
                shfmt
                wasm-pack
                zig
                runtime.node
                runtime.python
                runtime.erlang
                runtime.elixir
                runtime.swift
                runtime.swiftpm
              ])
              ++ runtime.swiftRuntime
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
              [ runtime.python ]
            else if stage == "c" || stage == "cpp" then
              with pkgs;
              [
                cmake
                gcc
              ]
            else if stage == "zig" then
              [ pkgs.zig ]
            else if stage == "typescript" then
              [ runtime.node ]
            else if stage == "python" then
              [ runtime.python ]
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
                runtime.erlang
                pkgs.rebar3
              ]
            else if stage == "erlang" then
              [
                runtime.erlang
                pkgs.rebar3
              ]
            else if stage == "elixir" then
              [
                runtime.erlang
                runtime.elixir
                pkgs.rebar3
              ]
            else if stage == "java" || stage == "kotlin" then
              [
                pkgs.jdk17
                pkgs.maven
              ]
            else if stage == "ruby" then
              [ pkgs.ruby ]
            else if stage == "php" then
              [ pkgs.php ]
            else if stage == "swift" then
              [
                runtime.swift
                runtime.swiftpm
              ]
              ++ runtime.swiftRuntime
            else
              throw "unknown zed-clients agent-check stage: ${stage}";
        in
        pkgs.lib.unique (commonToolchainFor pkgs ++ focused);

      fullToolchainFor =
        pkgs:
        let
          runtime = runtimePackagesFor pkgs;
        in
        pkgs.lib.unique (
          commonToolchainFor pkgs
          ++ (with pkgs; [
            actionlint
            cargo
            cmake
            curl
            dart
            gcc
            gleam
            go
            jdk17
            maven
            nix
            nixfmt
            openssl
            pkg-config
            rebar3
            ruby
            php
            rustc
            rustfmt
            shellcheck
            shfmt
            wasm-pack
            zig
          ])
          ++ [
            runtime.node
            runtime.python
            runtime.erlang
            runtime.elixir
            runtime.swift
            runtime.swiftpm
          ]
          ++ runtime.swiftRuntime
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
          runtime = runtimePackagesFor pkgs;
          agentCheck = self.packages.${system}.agentCheck;
          focusedShells = pkgs.lib.genAttrs stages (
            stage:
            import ./.nix/dev-shell.nix {
              inherit pkgs agentCheck;
              toolchain = stageToolchainFor pkgs stage;
              swiftCompiler = if stage == "swift" || stage == "toolchains" then runtime.swift else null;
              swiftRuntime = if stage == "swift" || stage == "toolchains" then runtime.swiftRuntime else [ ];
            }
          );
        in
        focusedShells
        // {
          default = import ./.nix/dev-shell.nix {
            inherit pkgs agentCheck;
            toolchain = fullToolchainFor pkgs;
            swiftCompiler = runtime.swift;
            swiftRuntime = runtime.swiftRuntime;
          };
        }
      );
    };
}
