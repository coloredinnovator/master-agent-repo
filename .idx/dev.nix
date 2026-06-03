# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.11"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    # For building your agents and data processing pipelines
    pkgs.python3
    pkgs.python3Packages.pip

    # For creating web interfaces or APIs
    pkgs.nodejs_22

    # For interacting with GitHub
    pkgs.gh

    # For interacting with Google Cloud services
    pkgs.google-cloud-sdk

    # For Firebase Firestore
    pkgs.firebase-tools

    # For infrastructure as code
    pkgs.terraform

    # For handling zip files
    pkgs.unzip
  ];

  # Sets environment variables in the workspace
  env = {
    DEEPSEEK_API_KEY = "your-secret-key";
  };

  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      "google.gemini-cli-vscode-ide-companion"
      "ms-python.python"
      "hashicorp.terraform"
    ];

    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        # Open editors for the following files by default, if they exist:
        default.openFiles = [ ".idx/dev.nix" "README.md" ];
      };
    };
  };
}
