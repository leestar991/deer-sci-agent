"""Tests for LocalSandbox._build_path_env and execute_command env var injection."""

import os
import sys
import textwrap

import pytest

from deerflow.sandbox.local.local_sandbox import LocalSandbox


class TestBuildPathEnv:
    def test_empty_mappings_returns_empty_dict(self):
        sb = LocalSandbox(id="t")
        assert sb._build_path_env() == {}

    def test_converts_virtual_path_to_env_var_name(self):
        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/workspace": "/phys/workspace",
            "/mnt/user-data/outputs":   "/phys/outputs",
            "/mnt/user-data/uploads":   "/phys/uploads",
            "/mnt/skills":              "/phys/skills",
        })
        env = sb._build_path_env()
        assert env["MNT_USER_DATA_WORKSPACE"] == "/phys/workspace"
        assert env["MNT_USER_DATA_OUTPUTS"]   == "/phys/outputs"
        assert env["MNT_USER_DATA_UPLOADS"]   == "/phys/uploads"
        assert env["MNT_SKILLS"]              == "/phys/skills"

    def test_no_extra_keys(self):
        sb = LocalSandbox(id="t", path_mappings={"/mnt/user-data/outputs": "/p"})
        env = sb._build_path_env()
        assert list(env.keys()) == ["MNT_USER_DATA_OUTPUTS"]


@pytest.mark.skipif(sys.platform == "win32", reason="Shell test uses Unix subprocess")
class TestExecuteCommandPathEnvInjection:
    def test_path_env_available_in_subprocess(self, tmp_path):
        """The MNT_* env vars must be present in the subprocess (verified by writing a
        file using the env var, not by echoing — echo output is reverse-resolved back
        to the virtual path by the sandbox, which is the correct/expected behaviour)."""
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()

        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/outputs": str(outputs_dir),
        })

        # Write a temp script and run it — avoids shell quoting nightmares.
        probe_script = tmp_path / "probe.py"
        probe_script.write_text(
            "import os\n"
            "p = os.environ.get('MNT_USER_DATA_OUTPUTS', 'MISSING')\n"
            "open(p + '/probe.txt', 'w').write('hit')\n"
            "print('wrote', p)\n"
        )
        result = sb.execute_command(f"python3 {probe_script}")
        # Output is reverse-resolved (physical → virtual), but the file exists
        assert (outputs_dir / "probe.txt").read_text() == "hit"

    def test_python_script_uses_env_var_to_write_output(self, tmp_path):
        """A Python script using os.environ.get('MNT_USER_DATA_OUTPUTS') should
        be able to create output files even when /mnt/user-data is not mounted."""
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()

        script_path = tmp_path / "write_test.py"
        script_path.write_text(textwrap.dedent(f"""
            import os
            OUTPUTS_DIR = os.environ.get("MNT_USER_DATA_OUTPUTS") or "/mnt/user-data/outputs"
            target = os.path.join(OUTPUTS_DIR, "result.txt")
            with open(target, "w") as f:
                f.write("ok")
            print("wrote:", target)
        """))

        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/outputs": str(outputs_dir),
        })

        result = sb.execute_command(f"python3 {script_path}")
        assert "wrote:" in result
        assert (outputs_dir / "result.txt").read_text() == "ok"

    def test_existing_env_vars_are_preserved(self, tmp_path):
        """User environment variables should not be wiped when injecting path vars."""
        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/outputs": str(tmp_path),
        })
        # PATH must still be present so commands like 'python3' resolve
        result = sb.execute_command("echo $PATH")
        assert len(result.strip()) > 0

    def test_pythonpath_prepended_when_workspace_mapped(self, tmp_path):
        """PYTHONPATH should include the workspace dir when workspace is mapped,
        so sitecustomize.py written there is auto-loaded by Python."""
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/workspace": str(workspace_dir),
            "/mnt/user-data/outputs":   str(tmp_path / "outputs"),
        })
        env = sb._build_path_env()
        assert "PYTHONPATH" in env
        assert str(workspace_dir) in env["PYTHONPATH"]

    def test_pythonpath_not_added_without_workspace(self):
        """PYTHONPATH should not be added if workspace is not in path_mappings."""
        sb = LocalSandbox(id="t", path_mappings={"/mnt/user-data/outputs": "/p"})
        env = sb._build_path_env()
        assert "PYTHONPATH" not in env

    def test_sitecustomize_patches_hardcoded_mnt_paths(self, tmp_path):
        """Scripts with hardcoded /mnt/... paths must work via sitecustomize.py
        path patching — including io.open (used by zipfile/pptx internally)."""
        workspace_dir = tmp_path / "workspace"
        outputs_dir = tmp_path / "outputs"
        workspace_dir.mkdir()
        outputs_dir.mkdir()

        sb = LocalSandbox(id="t", path_mappings={
            "/mnt/user-data/workspace": str(workspace_dir),
            "/mnt/user-data/outputs":   str(outputs_dir),
        })

        # Script uses hardcoded /mnt/ paths (no env var pattern) and also
        # calls io.open directly (as pptx/zipfile does).
        script = workspace_dir / "hardcoded_test.py"
        script.write_text(textwrap.dedent("""
            import io, os
            # builtins.open with hardcoded path
            with open("/mnt/user-data/outputs/via_open.txt", "w") as f:
                f.write("builtins_ok")
            # io.open with hardcoded path (simulates zipfile / python-pptx internals)
            with io.open("/mnt/user-data/outputs/via_io_open.txt", "w") as f:
                f.write("io_open_ok")
            # os.makedirs with hardcoded path
            os.makedirs("/mnt/user-data/outputs/subdir", exist_ok=True)
            print("done")
        """))

        result = sb.execute_command(f"python3 {script}")
        assert "done" in result
        assert (outputs_dir / "via_open.txt").read_text() == "builtins_ok"
        assert (outputs_dir / "via_io_open.txt").read_text() == "io_open_ok"
        assert (outputs_dir / "subdir").is_dir()
