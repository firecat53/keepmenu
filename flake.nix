{
  description = "Dmenu/Rofi/Wofi frontend for Keepass databases";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["x86_64-linux" "i686-linux" "aarch64-linux"];
    forAllSystems = f:
      nixpkgs.lib.genAttrs systems (system:
        f {
          pkgs = nixpkgs.legacyPackages.${system};
        });
  in {
    devShells = forAllSystems ({pkgs}: {
      default = pkgs.mkShell {
        buildInputs = with pkgs; [
          pandoc
          python3Packages.venvShellHook
          uv
        ];
        venvDir = "./.venv";
        C_INCLUDE_PATH = "${pkgs.linuxHeaders}/include";
        HATCH_ENV_TYPE_VIRTUAL_UV_PATH = "${pkgs.uv}/bin/uv"; # use Nix uv instead of hatch downloaded binary
        shellHook = ''
          # Exported here rather than as a mkShell attribute, which Nix would
          # pass through literally as the string "$PYTHONPATH:$PWD".
          export PYTHONPATH="$PYTHONPATH:$PWD"
          venvShellHook
          alias keepmenu="python -m keepmenu"
        '';
        postVenvCreation = ''
          uv pip install hatch
          uv pip install -e '.[autotype]'
          # Prevent venv uv from overriding nixpkgs uv
          [ -f $(pwd)/.venv/bin/uv ] && rm $(pwd)/.venv/bin/uv*
        '';
      };
    });
    packages = forAllSystems ({pkgs}: {
      default = pkgs.python3Packages.buildPythonApplication {
        pname = "keepmenu";
        version = builtins.head (builtins.match
          ".*\n__version__ = \"([^\"]+)\".*"
          (builtins.readFile ./keepmenu/__init__.py));
        format = "pyproject";
        src = ./.;
        nativeBuildInputs = builtins.attrValues {
          inherit
            (pkgs.python3Packages)
            hatchling
            ;
        };
        # pynput is the `autotype` extra in pyproject.toml, not a hard
        # dependency. Kept here so the packaged app is fully featured.
        propagatedBuildInputs = builtins.attrValues {
          inherit
            (pkgs.python3Packages)
            python
            pykeepass
            pynput
            ;
        };
        meta = {
          description = "Dmenu/Rofi/Wofi frontend for Keepass databases";
          homepage = "https://github.com/firecat53/keepmenu";
          license = pkgs.lib.licenses.gpl3;
          maintainers = ["firecat53"];
          platforms = systems;
        };
      };
    });
  };
}
