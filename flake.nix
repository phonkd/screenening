{
  description = "Personal Hyprland laptop-and-dock layout TUI";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    monique = {
      url = "github:ToRvaLDz/monique";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, monique }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
    in {
      packages = eachSystem (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          default = pkgs.writeShellApplication {
            name = "screenening";
            runtimeInputs = [ pkgs.python3 pkgs.fzf pkgs.hyprland monique.packages.${system}.default ];
            text = ''
              exec python3 ${./screenening.py} "$@"
            '';
          };
        });
      apps = eachSystem (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/screenening";
          meta.description = "Arrange my laptop and two external screens";
        };
      });
      checks = eachSystem (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          layout = pkgs.runCommand "screenening-tests" {
            nativeBuildInputs = [ pkgs.python3 monique.packages.${system}.default ];
          } ''
            cp ${./screenening.py} screenening.py
            cp ${./test_screenening.py} test_screenening.py
            python3 -m unittest -v
            touch "$out"
          '';
          package = self.packages.${system}.default;
        });
      devShells = eachSystem (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          default = pkgs.mkShell {
            packages = [ pkgs.python3 pkgs.fzf pkgs.hyprland monique.packages.${system}.default ];
          };
        });
    };
}
