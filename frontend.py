import os
import shutil
import subprocess
import sys


def find_npm() -> str | None:
    """Find the npm executable reliably across platforms.

    On Windows, npm is typically npm.cmd or npm.exe.
    """
    candidates = ["npm"]
    if os.name == "nt":
        candidates = ["npm", "npm.cmd", "npm.exe"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def main() -> None:
    project_path = os.path.dirname(os.path.abspath(__file__))
    frontend_path = os.path.join(project_path, "frontend")

    if not os.path.isdir(frontend_path):
        print(f"Error: Frontend directory not found at: {frontend_path}")
        sys.exit(1)

    pkg_json = os.path.join(frontend_path, "package.json")
    if not os.path.isfile(pkg_json):
        print(
            "Error: package.json not found in the Frontend folder. "
            
        )
        sys.exit(1)

    npm_path = find_npm()
    if not npm_path:
        print("Error: npm was not found on PATH.")
        print("\nHow to fix:")
        print("1) Install Node.js (includes npm) from https://nodejs.org/en/download")
        print(
            "2) Close and reopen your terminal/VS Code so PATH updates are picked up."
        )
        print("3) Verify installation in PowerShell:")
        print("   node -v")
        print("   npm -v")
        sys.exit(127)

    try:
        print("Installing frontend dependencies (npm install)…")
        subprocess.run([npm_path, "install"], cwd=frontend_path, check=True)

        print("Starting development server (npm run dev)…")
        subprocess.run([npm_path, "run", "dev"], cwd=frontend_path, check=True)
    except subprocess.CalledProcessError as e:
        cmd_disp = " ".join(e.cmd) if isinstance(e.cmd, (list, tuple)) else str(e.cmd)
        print(f"Command failed with exit code {e.returncode}: {cmd_disp}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(
            "Error: Failed to execute npm. Ensure Node.js/npm is installed and on PATH."
        )
        sys.exit(127)


if __name__ == "__main__":
    main()
