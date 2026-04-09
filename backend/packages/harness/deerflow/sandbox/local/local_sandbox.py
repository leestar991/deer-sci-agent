import ntpath
import os
import shutil
import subprocess
from pathlib import Path

from deerflow.sandbox.local.list_dir import list_dir
from deerflow.sandbox.sandbox import Sandbox


class LocalSandbox(Sandbox):
    @staticmethod
    def _shell_name(shell: str) -> str:
        """Return the executable name for a shell path or command."""
        return shell.replace("\\", "/").rsplit("/", 1)[-1].lower()

    @staticmethod
    def _is_powershell(shell: str) -> bool:
        """Return whether the selected shell is a PowerShell executable."""
        return LocalSandbox._shell_name(shell) in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}

    @staticmethod
    def _is_cmd_shell(shell: str) -> bool:
        """Return whether the selected shell is cmd.exe."""
        return LocalSandbox._shell_name(shell) in {"cmd", "cmd.exe"}

    @staticmethod
    def _find_first_available_shell(candidates: tuple[str, ...]) -> str | None:
        """Return the first executable shell path or command found from candidates."""
        for shell in candidates:
            if os.path.isabs(shell):
                if os.path.isfile(shell) and os.access(shell, os.X_OK):
                    return shell
                continue

            shell_from_path = shutil.which(shell)
            if shell_from_path is not None:
                return shell_from_path

        return None

    def __init__(self, id: str, path_mappings: dict[str, str] | None = None):
        """
        Initialize local sandbox with optional path mappings.

        Args:
            id: Sandbox identifier
            path_mappings: Dictionary mapping container paths to local paths
                          Example: {"/mnt/skills": "/absolute/path/to/skills"}
        """
        super().__init__(id)
        self.path_mappings = path_mappings or {}

    def _resolve_path(self, path: str) -> str:
        """
        Resolve container path to actual local path using mappings.

        Args:
            path: Path that might be a container path

        Returns:
            Resolved local path
        """
        path_str = str(path)

        # Try each mapping (longest prefix first for more specific matches)
        for container_path, local_path in sorted(self.path_mappings.items(), key=lambda x: len(x[0]), reverse=True):
            if path_str == container_path or path_str.startswith(container_path + "/"):
                # Replace the container path prefix with local path
                relative = path_str[len(container_path) :].lstrip("/")
                resolved = str(Path(local_path) / relative) if relative else local_path
                return resolved

        # No mapping found, return original path
        return path_str

    def _reverse_resolve_path(self, path: str) -> str:
        """
        Reverse resolve local path back to container path using mappings.

        Args:
            path: Local path that might need to be mapped to container path

        Returns:
            Container path if mapping exists, otherwise original path
        """
        path_str = str(Path(path).resolve())

        # Try each mapping (longest local path first for more specific matches)
        for container_path, local_path in sorted(self.path_mappings.items(), key=lambda x: len(x[1]), reverse=True):
            local_path_resolved = str(Path(local_path).resolve())
            if path_str.startswith(local_path_resolved):
                # Replace the local path prefix with container path
                relative = path_str[len(local_path_resolved) :].lstrip("/")
                resolved = f"{container_path}/{relative}" if relative else container_path
                return resolved

        # No mapping found, return original path
        return path_str

    def _reverse_resolve_paths_in_output(self, output: str) -> str:
        """
        Reverse resolve local paths back to container paths in output string.

        Args:
            output: Output string that may contain local paths

        Returns:
            Output with local paths resolved to container paths
        """
        import re

        # Sort mappings by local path length (longest first) for correct prefix matching
        sorted_mappings = sorted(self.path_mappings.items(), key=lambda x: len(x[1]), reverse=True)

        if not sorted_mappings:
            return output

        # Create pattern that matches absolute paths
        # Match paths like /Users/... or other absolute paths
        result = output
        for container_path, local_path in sorted_mappings:
            local_path_resolved = str(Path(local_path).resolve())
            # Escape the local path for use in regex
            escaped_local = re.escape(local_path_resolved)
            # Match the local path followed by optional path components
            pattern = re.compile(escaped_local + r"(?:/[^\s\"';&|<>()]*)?")

            def replace_match(match: re.Match) -> str:
                matched_path = match.group(0)
                return self._reverse_resolve_path(matched_path)

            result = pattern.sub(replace_match, result)

        return result

    def _resolve_paths_in_command(self, command: str) -> str:
        """
        Resolve container paths to local paths in a command string.

        Args:
            command: Command string that may contain container paths

        Returns:
            Command with container paths resolved to local paths
        """
        import re

        # Sort mappings by length (longest first) for correct prefix matching
        sorted_mappings = sorted(self.path_mappings.items(), key=lambda x: len(x[0]), reverse=True)

        # Build regex pattern to match all container paths
        # Match container path followed by optional path components
        if not sorted_mappings:
            return command

        # Create pattern that matches any of the container paths.
        # The lookahead (?=/|$|...) ensures we only match at a path-segment boundary,
        # preventing /mnt/skills from matching inside /mnt/skills-extra.
        patterns = [re.escape(container_path) + r"(?=/|$|[\s\"';&|<>()])(?:/[^\s\"';&|<>()]*)?" for container_path, _ in sorted_mappings]
        pattern = re.compile("|".join(f"({p})" for p in patterns))

        def replace_match(match: re.Match) -> str:
            matched_path = match.group(0)
            return self._resolve_path(matched_path)

        return pattern.sub(replace_match, command)

    @staticmethod
    def _get_shell() -> str:
        """Detect available shell executable with fallback."""
        shell = LocalSandbox._find_first_available_shell(("/bin/zsh", "/bin/bash", "/bin/sh", "sh"))
        if shell is not None:
            return shell

        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            shell = LocalSandbox._find_first_available_shell(
                (
                    "pwsh",
                    "pwsh.exe",
                    "powershell",
                    "powershell.exe",
                    ntpath.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
                    "cmd.exe",
                )
            )
            if shell is not None:
                return shell

            raise RuntimeError("No suitable shell executable found. Tried /bin/zsh, /bin/bash, /bin/sh, `sh` on PATH, then PowerShell and cmd.exe fallbacks for Windows.")

        raise RuntimeError("No suitable shell executable found. Tried /bin/zsh, /bin/bash, /bin/sh, and `sh` on PATH.")

    # sitecustomize.py template — injected into workspace so Python auto-loads it
    # on startup, transparently redirecting any /mnt/… file I/O to real paths.
    _SITECUSTOMIZE_TEMPLATE = '''\
# Auto-generated by LocalSandbox — DO NOT EDIT
# Patches Python built-ins so that scripts using hardcoded /mnt/… paths
# transparently resolve to the real physical paths on this host.
import builtins as _b
import io as _io
import os as _o

_MNT_MAP = {
    "/mnt/user-data/outputs":   _o.environ.get("MNT_USER_DATA_OUTPUTS") or "",
    "/mnt/user-data/workspace": _o.environ.get("MNT_USER_DATA_WORKSPACE") or "",
    "/mnt/user-data/uploads":   _o.environ.get("MNT_USER_DATA_UPLOADS") or "",
    "/mnt/skills":              _o.environ.get("MNT_SKILLS") or "",
}
_MNT_MAP = {k: v for k, v in _MNT_MAP.items() if v}

def _remap(p):
    if isinstance(p, (str, bytes)):
        s = p.decode("utf-8", errors="replace") if isinstance(p, bytes) else p
        for virt, real in sorted(_MNT_MAP.items(), key=lambda x: -len(x[0])):
            if s == virt or s.startswith(virt + "/"):
                s = real + s[len(virt):]
                return s.encode("utf-8") if isinstance(p, bytes) else s
    return p

# Patch builtins.open (used by most Python code)
_real_open = _b.open
def _open_p(file, *a, **kw):
    return _real_open(_remap(file), *a, **kw)
_b.open = _open_p

# Patch io.open (used by zipfile, pptx, and other C-extension modules)
_real_io_open = _io.open
def _io_open_p(file, *a, **kw):
    return _real_io_open(_remap(file), *a, **kw)
_io.open = _io_open_p

_real_makedirs = _o.makedirs
def _makedirs_p(name, *a, **kw):
    return _real_makedirs(_remap(name), *a, **kw)
_o.makedirs = _makedirs_p

_real_mkdir = _o.mkdir
def _mkdir_p(path, *a, **kw):
    return _real_mkdir(_remap(path), *a, **kw)
_o.mkdir = _mkdir_p

_real_stat = _o.stat
def _stat_p(path, *a, **kw):
    return _real_stat(_remap(path), *a, **kw)
_o.stat = _stat_p

_real_exists = _o.path.exists
def _exists_p(path):
    return _real_exists(_remap(path))
_o.path.exists = _exists_p

_real_getsize = _o.path.getsize
def _getsize_p(path):
    return _real_getsize(_remap(path))
_o.path.getsize = _getsize_p
'''

    def _ensure_sitecustomize(self) -> str | None:
        """Write sitecustomize.py to the workspace dir and return its path.

        When the workspace dir is prepended to PYTHONPATH, Python automatically
        imports sitecustomize on startup, patching file I/O to redirect /mnt/…
        paths to the correct physical locations — regardless of whether the
        script uses env vars or hardcoded virtual paths.

        Returns the workspace physical path, or None if not configured.
        """
        workspace_virtual = "/mnt/user-data/workspace"
        workspace_real = self.path_mappings.get(workspace_virtual)
        if not workspace_real:
            return None
        workspace_path = Path(workspace_real)
        workspace_path.mkdir(parents=True, exist_ok=True)
        sc_path = workspace_path / "sitecustomize.py"
        sc_path.write_text(self._SITECUSTOMIZE_TEMPLATE, encoding="utf-8")
        return str(workspace_path)

    def _build_path_env(self) -> dict[str, str]:
        """Build environment variables exposing virtual→physical path mappings.

        Each container path becomes an env var so that Python scripts spawned
        inside a bash command can resolve virtual paths at runtime:

            /mnt/user-data/workspace  →  MNT_USER_DATA_WORKSPACE
            /mnt/user-data/outputs    →  MNT_USER_DATA_OUTPUTS
            /mnt/user-data/uploads    →  MNT_USER_DATA_UPLOADS

        Also prepends the workspace directory to PYTHONPATH so that the
        sitecustomize.py written there is automatically loaded by Python,
        transparently redirecting /mnt/… I/O to real paths even in scripts
        that don't use the env var pattern.
        """
        env: dict[str, str] = {}
        for container_path, local_path in self.path_mappings.items():
            key = container_path.lstrip("/").upper().replace("-", "_").replace("/", "_")
            env[key] = local_path

        # Prepend workspace to PYTHONPATH so sitecustomize.py is auto-loaded
        workspace_real = self.path_mappings.get("/mnt/user-data/workspace")
        if workspace_real:
            existing = os.environ.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{workspace_real}:{existing}" if existing else workspace_real

        return env

    def execute_command(self, command: str) -> str:
        # Ensure sitecustomize.py exists in workspace for transparent /mnt/ path patching
        self._ensure_sitecustomize()

        # Resolve container paths in command before execution
        resolved_command = self._resolve_paths_in_command(command)
        shell = self._get_shell()

        # Inject path-mapping env vars so that Python scripts spawned by the
        # command can resolve virtual paths without needing the sandbox layer.
        proc_env = {**os.environ, **self._build_path_env()}

        if os.name == "nt":
            if self._is_powershell(shell):
                args = [shell, "-NoProfile", "-Command", resolved_command]
            elif self._is_cmd_shell(shell):
                args = [shell, "/c", resolved_command]
            else:
                args = [shell, "-c", resolved_command]

            result = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=600,
                env=proc_env,
            )
        else:
            result = subprocess.run(
                resolved_command,
                executable=shell,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
                env=proc_env,
            )
        output = result.stdout
        if result.stderr:
            output += f"\nStd Error:\n{result.stderr}" if output else result.stderr
        if result.returncode != 0:
            output += f"\nExit Code: {result.returncode}"

        final_output = output if output else "(no output)"
        # Reverse resolve local paths back to container paths in output
        return self._reverse_resolve_paths_in_output(final_output)

    def list_dir(self, path: str, max_depth=2) -> list[str]:
        resolved_path = self._resolve_path(path)
        entries = list_dir(resolved_path, max_depth)
        # Reverse resolve local paths back to container paths in output
        return [self._reverse_resolve_paths_in_output(entry) for entry in entries]

    def read_file(self, path: str) -> str:
        resolved_path = self._resolve_path(path)
        try:
            with open(resolved_path, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            # Re-raise with the original path for clearer error messages, hiding internal resolved paths
            raise type(e)(e.errno, e.strerror, path) from None

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        resolved_path = self._resolve_path(path)
        try:
            dir_path = os.path.dirname(resolved_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            mode = "a" if append else "w"
            with open(resolved_path, mode, encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            # Re-raise with the original path for clearer error messages, hiding internal resolved paths
            raise type(e)(e.errno, e.strerror, path) from None

    def update_file(self, path: str, content: bytes) -> None:
        resolved_path = self._resolve_path(path)
        try:
            dir_path = os.path.dirname(resolved_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(resolved_path, "wb") as f:
                f.write(content)
        except OSError as e:
            # Re-raise with the original path for clearer error messages, hiding internal resolved paths
            raise type(e)(e.errno, e.strerror, path) from None
