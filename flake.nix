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
        PYTHONPATH = "$PYTHONPATH:$PWD";
        shellHook = ''
          venvShellHook
          alias keepmenu="python -m keepmenu"
        '';
        postVenvCreation = ''
          uv pip install hatch
          uv pip install -e .
          # Prevent venv uv from overriding nixpkgs uv
          [ -f $(pwd)/.venv/bin/uv ] && rm $(pwd)/.venv/bin/uv*
        '';
      };
    });
    packages = forAllSystems ({pkgs}: {
      default = pkgs.python3Packages.buildPythonApplication {
        name = "keepmenu";
        pname = "keepmenu";
        format = "pyproject";
        src = ./.;
        nativeBuildInputs = builtins.attrValues {
          inherit
            (pkgs)
            git
            ;
          inherit
            (pkgs.python3Packages)
            hatchling
            hatch-vcs
            ;
        };
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
