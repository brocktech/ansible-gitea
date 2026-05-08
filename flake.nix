{
  description = "Ansible Collection for Gitea API";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {

      devShells.${system}.default = pkgs.mkShell {
        name = "ansible-gitea";
        packages = with pkgs; [
          ansible
          yq
        ];
      };
    };
}
