{
  description = "Shared build and check kit for usdAeco libraries and native plugins";

  inputs = {
    aeco-toolchain.url = "github:criad-com/aeco-toolchain?ref=v0.4.0";
    # Test-only compatibility input; recorded under dependencies.json.fixtures.
    core.url = "github:criad-com/usdaeco-core?ref=v0.9.2";
    core.flake = false;
    nixpkgs.follows = "aeco-toolchain/nixpkgs";
  };

  outputs = { self, nixpkgs, aeco-toolchain, core }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      forSystem = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (pkgs) lib;
          python = pkgs.python3;
          py = python.pkgs;
          usd-dev = aeco-toolchain.packages.${system}.usd-dev;
          # usd-dev's bindings were compiled for this nixpkgs Python. Adapt
          # their existing installation to withPackages without rebuilding USD.
          usdPython = py.toPythonModule (pkgs.runCommand
            "usd-dev-python-bindings-${usd-dev.version}" { } ''
              mkdir -p "$out/${python.sitePackages}"
              ln -s ${usd-dev}/${python.sitePackages}/pxr "$out/${python.sitePackages}/pxr"
            '');
          kit = py.buildPythonPackage {
            pname = "usdaeco-toolchain";
            version = (builtins.fromJSON (builtins.readFile ./library.json)).version;
            pyproject = true;
            src = self;
            build-system = [ py.setuptools ];
            dependencies = [ py.packaging py.jinja2 py.numpy ];
            doCheck = false; # The flake's checks exercise the USD-enabled package.
            pythonImportsCheck = [ "usdaeco_check" "pluginset" ];
          };
          pythonEnv = python.withPackages (ps:
            [ usdPython kit ps.jinja2 ps.numpy ps.pytest ps.packaging ps.pillow ]
            ++ lib.optionals (ps ? ifcopenshell && !(ps.ifcopenshell.meta.broken or false))
              [ ps.ifcopenshell ]);
          nativePython = python.withPackages (ps: [ usdPython ps.jinja2 ps.packaging ]);

          buildCodelessSchema = { name, src, deps ? [ ] }:
            let
              closure = lib.unique (lib.concatMap (dep: [ dep ] ++ (dep.aecoDependencies or [ ])) deps);
            in pkgs.stdenvNoCC.mkDerivation {
              name = "${name}-codeless";
              inherit src;
              nativeBuildInputs = [ pythonEnv usd-dev ];
              dontConfigure = true;
              dontBuild = true;
              installPhase = ''
                runHook preInstall
                export PYTHON=${pythonEnv}/bin/python
                bash ${self}/build.sh ${lib.escapeShellArg name} "$PWD" --install-root "$out" \
                  ${lib.concatMapStringsSep " " (dep: "--dep " + lib.escapeShellArg (toString dep)) closure}
                runHook postInstall
              '';
              passthru.aecoDependencies = closure;
            };

          native = import ./nix/native.nix {
            inherit pkgs usd-dev;
            pythonEnv = nativePython;
            toolchainSrc = self;
          };

          pluginSet = { plugins, name ? "usdaeco-plugin-set" }:
            let
              closure = lib.unique (lib.concatMap (plugin:
                [ plugin ] ++ (plugin.aecoDependencies or [ ])) plugins);
            in pkgs.runCommand name { nativeBuildInputs = [ pythonEnv ]; } ''
              env -u PYTHONPATH ${pythonEnv}/bin/python ${self}/tools/pluginset.py "$out" \
                ${lib.escapeShellArgs (map toString closure)}
            '';
        in { inherit pkgs pythonEnv nativePython kit usd-dev usdPython buildCodelessSchema pluginSet;
          inherit (native) buildCodefulSchema buildNativePlugin;
        };
    in {
      lib = {
        inherit forSystem;
        buildCodelessSchema = { system ? builtins.currentSystem or "aarch64-darwin", ... }@args:
          (forSystem system).buildCodelessSchema (builtins.removeAttrs args [ "system" ]);
        buildCodefulSchema = { system ? builtins.currentSystem or "aarch64-darwin", ... }@args:
          (forSystem system).buildCodefulSchema (builtins.removeAttrs args [ "system" ]);
        buildNativePlugin = { system ? builtins.currentSystem or "aarch64-darwin", ... }@args:
          (forSystem system).buildNativePlugin (builtins.removeAttrs args [ "system" ]);
        pluginSet = { system ? builtins.currentSystem or "aarch64-darwin", ... }@args:
          (forSystem system).pluginSet (builtins.removeAttrs args [ "system" ]);
      };
      packages = eachSystem (system: let p = forSystem system; in {
        inherit (p) pythonEnv nativePython;
        default = p.kit;
        template-native-schema = p.buildCodefulSchema {
          name = "usdAecoExampleNative"; src = ./template-native/schema;
        };
        template-native-plugin = p.buildNativePlugin {
          name = "usdAecoExampleHello"; src = ./template-native/plugin;
        };
      });
      checks = eachSystem (system: let p = forSystem system; in {
        native-schema = self.packages.${system}.template-native-schema;
        native-plugin = self.packages.${system}.template-native-plugin;
        native-consumer = p.pkgs.runCommand "native-installed-cmake-consumer" {
          nativeBuildInputs = [ p.pkgs.cmake p.pkgs.ninja p.pkgs.stdenv.cc
            p.pkgs.opensubdiv.dev p.pkgs.opensubdiv.static ];
          buildInputs = [ self.packages.${system}.template-native-schema ];
        } ''
          cmake -S ${self}/template-native/schema/testenv/consumer -B build -G Ninja
          cmake --build build
          export PXR_PLUGINPATH_NAME=${self.packages.${system}.template-native-schema}/lib
          ctest --test-dir build --output-on-failure
          touch "$out"
        '';
        native-closure = p.pkgs.runCommand "native-occt-shared-closure" { } ''
          mkdir -p "$out"
          closure=${p.pkgs.closureInfo { rootPaths = [
            self.packages.${system}.template-native-schema
            self.packages.${system}.template-native-plugin
            aeco-toolchain.packages.${system}.occt
          ]; }}/store-paths
          while IFS= read -r store_path; do
            if find "$store_path" -name 'libTK*.a' -print -quit | grep -q .; then
              echo "static OCCT archive in native closure" >&2
              exit 1
            fi
          done < "$closure"
          printf 'closure paths=%s; static OCCT archives=0\n' \
            "$(wc -l < "$closure" | tr -d ' ')" > "$out/report.txt"
        '';
        python = p.pkgs.runCommand "usdaeco-toolchain-check" {
          nativeBuildInputs = [ p.pythonEnv p.usd-dev ];
        } ''
          export USDAECO_CORE_DIR=${core}
          export CORE_PLUGIN_DIR=${p.buildCodelessSchema { name = "usdAeco"; src = core; }}/plugins/usdAeco/resources
          export AECO_NATIVE_SCHEMA=${self.packages.${system}.template-native-schema}
          export AECO_NATIVE_PLUGIN=${self.packages.${system}.template-native-plugin}
          export AECO_NATIVE_PYTHON=${p.pythonEnv}/bin/python3
          export AECO_USD_PYTHON=${p.usd-dev}/${p.pkgs.python3.sitePackages}
          cp -R ${self} source
          chmod -R u+w source
          cd source
          env -u PYTHONPATH python -c 'from pxr import Usd; import jinja2, numpy, pytest; print(Usd.GetVersion())'
          env -u PYTHONPATH python check.py
          mkdir -p "$out"
        '';
      });
      devShells = eachSystem (system: let p = forSystem system; in {
        default = p.pkgs.mkShell {
          packages = [ p.pythonEnv p.usd-dev ];
          shellHook = "unset PYTHONPATH; export PYTHON=python3";
        };
      });
    };
}
