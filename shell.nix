{ sources ? import ./nix/sources.nix }:

with import sources.nixpkgs {};

mkShell {
  name = "devel";
  buildInputs = [
    niv
    age
    glibcLocales
    autoPatchelfHook

    # Python
    python312

    # Package management
    uv

    # Linting & formatting
    ruff
    mypy

    # Google Cloud
    google-cloud-sdk

    # Testing
    curl
  ];
  shellHook =
    let
      libs = [
        pkgs.gcc-unwrapped.lib
        pkgs.zlib
      ];
    in
    ''
      unset PYTHONPATH
      # set SOURCE_DATE_EPOCH so that we can use python wheels
      export SOURCE_DATE_EPOCH=315532800
      # export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath libs}"
    '';
  preferLocalBuild = true;
}
