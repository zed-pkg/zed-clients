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
      toolchainFor =
        pkgs:
        let
          node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
          python = pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs;
          erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
          swiftToolchain = [
            pkgs.swiftPackages.swift
            pkgs.swiftPackages.swiftpm
          ];
        in
        (with pkgs; [
          actionlint
          bash
          cacert
          cargo
          coreutils
          curl
          dart
          findutils
          gawk
          gcc
          git
          gleam
          gnugrep
          gnused
          go
          gzip
          jdk17
          jq
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
          unzip
          wasm-pack
        ])
        ++ [ erlang ]
        ++ swiftToolchain;
    in
    {
      formatter = forAllSystems (system: (pkgsFor system).nixfmt);

      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          swiftCompiler = pkgs.swiftPackages.swift;
          swiftLibraryPath = swiftLibraryPathFor pkgs;
          agentCheck = pkgs.writeShellApplication {
            name = "agent-check";
            runtimeInputs = toolchainFor pkgs;
            text = ''
              export SWIFT_EXEC="${swiftCompiler}/bin/swiftc"
              export LD_LIBRARY_PATH="${swiftLibraryPath}:''${LD_LIBRARY_PATH:-}"
              ${builtins.readFile ./.nix/agent-check.sh}
            '';
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
          swiftRuntime = swiftRuntimeFor pkgs;
        in
        {
          default = import ./.nix/dev-shell.nix {
            inherit pkgs swiftRuntime;
            agentCheck = self.packages.${system}.agentCheck;
            toolchain = toolchainFor pkgs;
            swiftCompiler = pkgs.swiftPackages.swift;
            swiftLibraryPath = swiftLibraryPathFor pkgs;
          };
        }
      );
    };
}
