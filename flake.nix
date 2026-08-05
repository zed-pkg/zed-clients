{
  description = "Agent-first development environment for the zed-pkg client SDK matrix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    swift-compat.url = "github:NixOS/nixpkgs/70bdadeb94ffc8806c0570eb5c2695ad29f0e421";
  };

  outputs =
    {
      self,
      nixpkgs,
      swift-compat,
      ...
    }:
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
      swiftRelease = import ./.nix/swift-release.nix;
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };
      swiftCompatPkgsFor = system: import swift-compat { inherit system; };

      agentCheckFor = pkgs: pkgs.writeShellApplication {
        name = "agent-check";
        runtimeInputs = [ pkgs.bash ];
        text = builtins.readFile ./.nix/agent-check.sh;
      };

      officialSwiftFor =
        compat:
        let
          release = swiftRelease.${compat.system};
        in
        compat.stdenv.mkDerivation {
          pname = "swift";
          inherit (swiftRelease) version;
          src = compat.fetchurl {
            inherit (release) url hash;
          };

          nativeBuildInputs = [ compat.autoPatchelfHook ];
          buildInputs = [
            compat.curl
            compat.icu
            compat.libbsd
            compat.libedit
            compat.libuuid
            compat.libxml2
            compat.ncurses
            compat.python310
            compat.sqlite
            compat.stdenv.cc.cc.lib
            compat.zlib
          ];

          dontConfigure = true;
          dontBuild = true;
          dontStrip = true;

          installPhase = ''
            runHook preInstall
            mv usr "$out"
            ln -s ${compat.libedit}/lib/libedit.so "$out/lib/libedit.so.2"
            runHook postInstall
          '';

          meta = {
            description = "Official Swift ${swiftRelease.version} Ubuntu 22.04 toolchain";
            homepage = "https://www.swift.org/";
            license = compat.lib.licenses.asl20;
            sourceProvenance = [ compat.lib.sourceTypes.binaryBytecode ];
            platforms = [
              "x86_64-linux"
              "aarch64-linux"
            ];
            mainProgram = "swift";
          };
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

      currentStageToolchainFor =
        pkgs: stage:
        let
          node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
          python = pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs;
          erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
          focused =
            if stage == "toolchains" then
              with pkgs;
              [
                actionlint
                cargo
                dart
                erlang
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
            else
              throw "unknown current-Nixpkgs stage: ${stage}";
        in
        pkgs.lib.unique (commonToolchainFor pkgs ++ focused);

      fullCurrentToolchainFor =
        pkgs:
        let
          node = pkgs.lib.attrByPath [ "nodejs_22" ] pkgs.nodejs pkgs;
          python = pkgs.lib.attrByPath [ "python312" ] pkgs.python3 pkgs;
          erlang = pkgs.lib.attrByPath [ "beam27Packages" "erlang" ] pkgs.erlang pkgs;
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
          ++ [ erlang ]
          ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
            pkgs.swiftPackages.swift
            pkgs.swiftPackages.swiftpm
          ]
        );
    in
    {
      formatter = forAllSystems (system: (pkgsFor system).nixfmt);

      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          agentCheck = agentCheckFor pkgs;
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
          focusedShells = pkgs.lib.genAttrs stages (
            stage:
            if stage == "swift" && pkgs.stdenv.hostPlatform.isLinux then
              let
                compat = swiftCompatPkgsFor system;
                swift = officialSwiftFor compat;
                swiftAgentCheck = agentCheckFor compat;
              in
              import ./.nix/dev-shell.nix {
                pkgs = compat;
                agentCheck = swiftAgentCheck;
                toolchain = compat.lib.unique (commonToolchainFor compat ++ [ swift ]);
                swiftCompiler = swift;
              }
            else if stage == "swift" then
              import ./.nix/dev-shell.nix {
                inherit pkgs agentCheck;
                toolchain = pkgs.lib.unique (
                  commonToolchainFor pkgs
                  ++ [
                    pkgs.swiftPackages.swift
                    pkgs.swiftPackages.swiftpm
                  ]
                );
                swiftCompiler = pkgs.swiftPackages.swift;
              }
            else
              import ./.nix/dev-shell.nix {
                inherit pkgs agentCheck;
                toolchain = currentStageToolchainFor pkgs stage;
              }
          );
        in
        focusedShells
        // {
          default = import ./.nix/dev-shell.nix {
            inherit pkgs agentCheck;
            toolchain = fullCurrentToolchainFor pkgs;
            swiftCompiler =
              if pkgs.stdenv.hostPlatform.isDarwin then pkgs.swiftPackages.swift else null;
          };
        }
      );
    };
}
