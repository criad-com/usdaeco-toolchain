{
  description = "usdaeco-example companion repository";
  inputs = {
    toolchain.url = "github:criad-com/usdaeco-toolchain?ref=v0.3.8";
    nixpkgs.follows = "toolchain/nixpkgs";
  };
  outputs = { self, nixpkgs, toolchain }:
    let
      eachSystem = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ];
    in {
      packages = eachSystem (system: let
        kit = toolchain.lib.forSystem system;
        py = nixpkgs.legacyPackages.${system}.python3Packages;
      in {
        default = py.buildPythonPackage {
          pname = "usdaeco-example";
          version = (builtins.fromJSON (builtins.readFile ./library.json)).version;
          src = self;
          pyproject = true;
          build-system = [ py.setuptools ];
          dependencies = [ kit.kit ];
          doCheck = false;
        };
      });
      checks = eachSystem (system: let kit = toolchain.lib.forSystem system; in {
        structure = kit.pkgs.runCommand "usdaeco-example-structure" {
          nativeBuildInputs = [ kit.pythonEnv ];
        } ''
          env -u PYTHONPATH python ${self}/check.py
          mkdir -p "$out"
        '';
      });
      devShells = eachSystem (system: let kit = toolchain.lib.forSystem system; in {
        default = kit.pkgs.mkShell { packages = [ kit.pythonEnv ]; };
      });
    };
}
