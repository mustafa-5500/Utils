"""
PlantUML PNG Renderer for Decomposition Diagrams.

Converts the `.puml` decomposition diagrams produced by `generate_decomp.py`
into PNG images using PlantUML.

Backends (only one is used per run):
  1. A PlantUML server (`--server URL`), useful with a locally hosted or
     Docker-based plantuml-server.
  2. A local `plantuml.jar` (requires Java). The jar is located in this order:
       - the `--plantuml-jar` argument
       - the `PLANTUML_JAR` environment variable
       - `plantuml.jar` next to this script
       - `~/.plantuml/plantuml.jar`
     If none is found, the latest release is downloaded to `~/.plantuml/`
     automatically (disable with `--no-download`).

Usage:
    python render_decomp_png.py <puml_path> [output_folder] [options]

Arguments:
    <puml_path>      A `.puml` file, or a directory to scan recursively.
    [output_folder]  Where PNGs are written, mirroring the directory layout.
                     Defaults to writing each PNG next to its `.puml` file.

Options:
    --plantuml-jar PATH   Path to a local plantuml.jar.
    --server URL          PlantUML server base URL (e.g. http://localhost:8080).
    --no-download         Don't auto-download plantuml.jar.

Examples:
    python render_decomp_png.py ../Documentation
    python render_decomp_png.py ../Documentation ../Documentation/images
    python render_decomp_png.py ../Documentation --server http://localhost:8080
"""

import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar"


def usage() -> None:
    """Print usage information for the script."""
    print("Usage: python render_decomp_png.py <puml_path> [output_folder] [options]")
    print("<puml_path> may be a single .puml file or a directory scanned recursively.")
    print("Options: --plantuml-jar PATH | --server URL | --no-download")


def collect_puml_files(path: Path) -> list[Path]:
    """Return all .puml files under `path` (or just `path` if it is a file)."""
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.puml"))


def group_by_directory(files: list[Path]) -> dict[Path, list[Path]]:
    """Group files by their parent directory so each directory renders in one JVM run."""
    groups: dict[Path, list[Path]] = {}
    for f in files:
        groups.setdefault(f.parent, []).append(f)
    return groups


def java_available() -> bool:
    """Return True if `java` can be launched."""
    try:
        subprocess.run(["java", "-version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def download_plantuml_jar(destination: Path) -> Path:
    """Download the latest plantuml.jar to `destination` and return its path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading plantuml.jar from {PLANTUML_JAR_URL} ...")
    urllib.request.urlretrieve(PLANTUML_JAR_URL, destination)
    print(f"Downloaded to {destination}")
    return destination


def locate_plantuml_jar(jar_arg: str | None, allow_download: bool) -> Path | None:
    """Resolve the plantuml.jar location, downloading it if necessary."""
    if jar_arg:
        explicit = Path(jar_arg).expanduser()
        if explicit.is_file():
            print(f"Using plantuml.jar: {explicit}")
            return explicit.resolve()
        print(f"plantuml.jar not found at: {explicit}")
        return None

    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        env_path = Path(env_jar).expanduser()
        if env_path.is_file():
            print(f"Using plantuml.jar: {env_path}")
            return env_path.resolve()

    script_dir = Path(__file__).resolve().parent
    local_jar = script_dir / "plantuml.jar"
    if local_jar.is_file():
        print(f"Using plantuml.jar: {local_jar}")
        return local_jar

    cache_jar = Path.home() / ".plantuml" / "plantuml.jar"
    if cache_jar.is_file():
        print(f"Using plantuml.jar: {cache_jar}")
        return cache_jar

    if allow_download:
        print("No plantuml.jar found. Downloading the latest release...")
        try:
            return download_plantuml_jar(cache_jar)
        except Exception as exc:  # noqa: BLE001 - report any download failure
            print(f"Download failed: {exc}")
    return None


def expected_output_path(source: Path, out_root: Path | None, puml_root: Path) -> Path:
    """Compute where a rendered PNG should be written for a given .puml file."""
    if out_root is None:
        return source.with_suffix(".png")
    try:
        relative = source.relative_to(puml_root)
    except ValueError:
        relative = Path(source.name)
    return out_root / relative.with_suffix(".png")


def render_with_jar(jar: Path, files: list[Path], out_root: Path | None, puml_root: Path) -> int:
    """Render .puml files to PNG using a local plantuml.jar."""
    rendered = 0
    for directory, group in sorted(group_by_directory(files).items()):
        command = ["java", "-jar", str(jar), "-tpng", "-charset", "UTF-8"]
        if out_root is not None:
            try:
                rel_dir = directory.relative_to(puml_root)
            except ValueError:
                rel_dir = Path()
            target = out_root / rel_dir
            target.mkdir(parents=True, exist_ok=True)
            command += ["-o", str(target)]
        command += [str(f) for f in group]

        print("Running: " + " ".join(command))
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"PlantUML failed ({exc.returncode}) for directory: {directory}")
            continue

        for source in group:
            output = expected_output_path(source, out_root, puml_root)
            if output.exists():
                print(f"Rendered: {output}")
                rendered += 1
            else:
                print(f"WARNING: expected output missing: {output}")

    return rendered


def render_with_server(base_url: str, files: list[Path], out_root: Path | None, puml_root: Path) -> int:
    """Render .puml files to PNG using a PlantUML server's /form endpoint."""
    endpoint = base_url.rstrip("/") + "/form"
    rendered = 0
    for source in files:
        text = source.read_text(encoding="utf-8")
        data = urllib.parse.urlencode({"text": text}).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = response.read()
        except Exception as exc:  # noqa: BLE001 - report any network error
            print(f"Failed to render {source}: {exc}")
            continue

        if not payload.startswith(b"\x89PNG"):
            print(f"Server did not return a PNG for {source} "
                  f"(got {len(payload)} bytes). Is the server URL correct?")
            continue

        output = expected_output_path(source, out_root, puml_root)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        print(f"Rendered: {output}")
        rendered += 1

    return rendered


def main() -> int:
    """Parse arguments and render the requested PlantUML files to PNG."""
    jar_arg: str | None = None
    server: str | None = None
    allow_download = True
    positional: list[str] = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            usage()
            return 0
        if arg == "--plantuml-jar":
            i += 1
            if i < len(args):
                jar_arg = args[i]
        elif arg == "--server":
            i += 1
            if i < len(args):
                server = args[i]
        elif arg == "--no-download":
            allow_download = False
        else:
            positional.append(arg)
        i += 1

    if not positional:
        usage()
        return 1

    puml_path = Path(positional[0]).resolve()
    out_root = Path(positional[1]).resolve() if len(positional) > 1 else None

    if not puml_path.exists():
        print(f"Path not found: {puml_path}")
        return 1

    files = collect_puml_files(puml_path)
    if not files:
        print(f"No .puml files found under: {puml_path}")
        return 0

    puml_root = puml_path if puml_path.is_dir() else puml_path.parent
    print(f"Found {len(files)} PlantUML file(s) to render.")

    if server:
        rendered = render_with_server(server, files, out_root, puml_root)
    else:
        jar = locate_plantuml_jar(jar_arg, allow_download)
        if jar is None:
            print("No plantuml.jar available. Download it from "
                  "https://github.com/plantuml/plantuml/releases/latest and pass "
                  "--plantuml-jar <path>, or set the PLANTUML_JAR environment variable.")
            return 1
        if not java_available():
            print("Java is required to run plantuml.jar, but 'java' was not found on the PATH.")
            return 1
        rendered = render_with_jar(jar, files, out_root, puml_root)

    print(f"Done. Rendered {rendered} PNG(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
