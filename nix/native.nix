{ pkgs, usd-dev, pythonEnv, toolchainSrc }:
let
  inherit (pkgs) lib;
  dependencyClosure = deps: lib.unique (lib.concatMap
    (dep: [ dep ] ++ (dep.aecoDependencies or [ ])) deps);
  build = codeful: { name, src, deps ? [ ], cmakeFlags ? [ ] }:
    let
      closure = dependencyClosure deps;
      plugins = builtins.filter (dep: dep ? aecoDependencies) closure;
    in pkgs.stdenv.mkDerivation {
      pname = name;
      version = (builtins.fromJSON (builtins.readFile (src + /library.json))).version;
      inherit src;
      nativeBuildInputs = [ pkgs.cmake pkgs.ninja pythonEnv usd-dev
        pkgs.opensubdiv.dev pkgs.opensubdiv.static ];
      propagatedBuildInputs = [ usd-dev ] ++ closure;
      cmakeFlags = [
        "-DBUILD_SHARED_LIBS=ON"
        "-DAECO_NATIVE_CMAKE=${toolchainSrc}/cmake"
        "-DAECO_USD_PYTHON=${usd-dev}/${pkgs.python3.sitePackages}"
        "-DAECO_PYTHON_INSTALL_DIR=${pkgs.python3.sitePackages}"
        "-DPython3_EXECUTABLE=${pythonEnv}/bin/python3"
        "-DPython3_INCLUDE_DIR=${pkgs.python3}/include/${pkgs.python3.libPrefix}"
        "-DPython3_LIBRARY=${pkgs.python3}/lib/lib${pkgs.python3.libPrefix}${pkgs.stdenv.hostPlatform.extensions.sharedLibrary}"
      ] ++ cmakeFlags;
      preConfigure = lib.optionalString codeful ''
        echo "== stage: codeful schema generation"
        env -u PYTHONPATH ${pythonEnv}/bin/python ${toolchainSrc}/tools/build_codeful_schema.py \
          ${lib.escapeShellArg name} "$PWD" --generator ${usd-dev}/${pkgs.python3.sitePackages}/pxr/Usd/usdGenSchema.py \
          ${lib.concatMapStringsSep " " (dep: "--dep " + lib.escapeShellArg (toString dep)) plugins}
      '';
      doCheck = true;
      checkPhase = ''
        runHook preCheck
        echo "== stage: native build-tree tests"
        ctest --output-on-failure --no-tests=error
        runHook postCheck
      '';
      postInstall = ''
        test -f "$out/lib/lib${name}${pkgs.stdenv.hostPlatform.extensions.sharedLibrary}"
        test -f "$out/lib/${name}/resources/plugInfo.json"
        test -f "$out/lib/cmake/${name}/${name}Config.cmake"
        test -f "$out/lib/plugInfo.json"
      '';
      postFixup = ''
        echo "== stage: native OCCT archive policy"
        closure=${pkgs.closureInfo { rootPaths = [ usd-dev ] ++ closure; }}/store-paths
        for store_path in "$out" $(cat "$closure"); do
          pattern='libTK*.a'
          case "$store_path" in
            *opencascade*|*occt*) pattern='*.a' ;;
          esac
          if find "$store_path" -name "$pattern" -print -quit | grep -q .; then
            echo "static OCCT archive in native consumer closure" >&2
            exit 1
          fi
        done
      '';
      passthru.aecoDependencies = plugins;
    };
in {
  buildCodefulSchema = build true;
  buildNativePlugin = build false;
}
