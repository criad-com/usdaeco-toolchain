{
  description = "usdAecoExample semantic library and example";
  inputs = {
    toolchain.url = "github:criad-com/usdaeco-toolchain?ref=v0.3.8";
    nixpkgs.follows = "toolchain/nixpkgs";
    core.url = "github:criad-com/usdaeco-core?ref=v0.9.3";
    core.inputs.toolchain.follows = "toolchain";
    core.inputs.nixpkgs.follows = "nixpkgs";
    datacentre.url = "github:criad-com/usdaeco-datacentre?ref=v0.4.6";
    datacentre.flake = false;
  };
  outputs = { self, nixpkgs, toolchain, core, datacentre }:
    let
      eachSystem = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ];
      forSystem = system:
        let
          kit = toolchain.lib.forSystem system;
          pkgs = nixpkgs.legacyPackages.${system};
          corePlugin = core.packages.${system}.default;
          schema = kit.buildCodelessSchema { name = "usdAecoExample"; src = self; deps = [ corePlugin ]; };
          plugins = kit.pluginSet { plugins = [ schema ]; };
          setup = ''
            export TOOLCHAIN_DIR=${toolchain}
            export CORE_PLUGIN_DIR=${corePlugin}/plugins/usdAeco/resources
            export AECO_DATACENTRE_ROOT=${datacentre}
            export PXR_PLUGINPATH_NAME=${plugins}
          '';
          example = pkgs.writeShellApplication {
            name = "example";
            runtimeInputs = [ kit.pythonEnv kit.usd-dev ];
            text = setup + ''
              cp -R ${self} example-work
              chmod -R u+w example-work
              env -u PYTHONPATH python example-work/examples/datacentre/run.py "$@"
            '';
          };
          render = pkgs.writeShellApplication {
            name = "render";
            runtimeInputs = [ kit.pythonEnv kit.usd-dev ];
            text = setup + ''
              env -u PYTHONPATH usdaeco-render ${self}/usdAecoExample/examples/minimal.usda \
                --cameras ${self}/examples/datacentre/inputs/cameras.usda "$@"
            '';
          };
        in { inherit kit pkgs schema plugins setup example render; };
    in {
      packages = eachSystem (system: let p = forSystem system; in {
        default = p.schema;
        pluginSet = p.plugins;
      });
      checks = eachSystem (system: let p = forSystem system; in {
        library = p.pkgs.runCommand "usdAecoExample-check" {
          nativeBuildInputs = [ p.kit.pythonEnv p.kit.usd-dev ];
        } (p.setup + ''
          cp -R ${self} source
          chmod -R u+w source
          cd source
          env -u PYTHONPATH python check.py
          mkdir -p "$out"
        '');
        structure = p.pkgs.runCommand "usdAecoExample-structure" {
          nativeBuildInputs = [ p.kit.pythonEnv ];
        } (p.setup + ''
          env -u PYTHONPATH usdaeco-check structure ${self}
          mkdir -p "$out"
        '');
      });
      devShells = eachSystem (system: let p = forSystem system; in {
        default = p.pkgs.mkShell {
          packages = [ p.kit.pythonEnv p.kit.usd-dev ];
          shellHook = p.setup + "unset PYTHONPATH";
        };
      });
      apps = eachSystem (system: let p = forSystem system; in {
        example = { type = "app"; program = "${p.example}/bin/example"; };
        render = { type = "app"; program = "${p.render}/bin/render"; };
      });
    };
}
