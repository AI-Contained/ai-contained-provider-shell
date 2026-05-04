{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages.default = pkgs.buildEnv {
          name = "ai-contained-provider-shell";
          paths = [ pkgs.gitMinimal ];
        };

        devShells.default = pkgs.mkShell {
          packages = [ pkgs.gitMinimal pkgs.python312 ];
        };
      }
    );
}
