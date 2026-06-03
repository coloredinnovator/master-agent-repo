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
    pkgs.jupyter

    # Core data science and machine learning libraries
    pkgs.python3Packages.numpy
    pkgs.python3Packages.pandas
    pkgs.python3Packages.scipy
    pkgs.python3Packages.scikitlearn
    pkgs.python3Packages.matplotlib

    # Hugging Face ecosystem for state-of-the-art AI models
    pkgs.python3Packages.transformers
    pkgs.python3Packages.datasets
    pkgs.python3Packages.accelerate
    pkgs.python3Packages.diffusers

    # For geospatial data analysis
    pkgs.gdal

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
    # Add your Hugging Face token for private models and other features
    # HUGGING_FACE_HUB_TOKEN = "your-hugging-face-token";
    # GITHUB_TOKEN = "your-github-token";
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
