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
        f rec {
          pkgs = nixpkgs.legacyPackages.${system};
          commonPackages = builtins.attrValues {
            inherit
              (pkgs.python3Packages)
              python
              pykeepass
              pynput
              ;
          };
        });
  in {
    devShells = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
      default = pkgs.mkShell {
        packages = commonPackages ++ [pkgs.pandoc];
        shellHook = ''
          alias keepmenu="python -m keepmenu"
          export PYTHONPATH="$PYTHONPATH:$PWD"
        '';
      };
    });
    packages = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
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
        propagatedBuildInputs = commonPackages;
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
