{ pkgs, ... }: {
  channel = "stable-24.11";
  packages = [ pkgs.terraform pkgs.google-cloud-sdk pkgs.git ];
  idx = {
    extensions = [
      "mhutchie.git-graph"
      "github.copilot"
      "github.copilot-chat"
      "ms-python.python"
      "ms-python.debugpy"
    ];
    workspace = {
      onCreate = {
        default.openFiles = [ ".idx/dev.nix" "README.md" ];
      };
    };
  };
}
