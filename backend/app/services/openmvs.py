"""OpenMVS dense reconstruction from OpenMVG output."""

import subprocess
from pathlib import Path
from typing import Callable, Optional

from app.config import settings


class OpenMVSService:
    """Wraps OpenMVS CLI tools for dense point cloud and mesh generation."""

    DENSE_TOOLS = (
        "DensifyPointCloud",
        "ReconstructMesh",
        "TextureMesh",
    )

    def __init__(self) -> None:
        self.bin_dir = settings.openmvs_bin_dir

    @property
    def is_configured(self) -> bool:
        if not self.bin_dir or not self.bin_dir.is_dir():
            return False
        return all((self.bin_dir / tool).exists() for tool in self.DENSE_TOOLS)

    def _binary(self, name: str) -> Path:
        if not self.bin_dir:
            raise RuntimeError("OPENMVS_BIN_DIR is not set")
        path = self.bin_dir / name
        if not path.exists():
            raise FileNotFoundError(f"OpenMVS binary not found: {path}")
        return path

    def _run(self, cmd: list[str], cwd: Path) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(cwd))
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"{cmd[0].split('/')[-1]} failed (exit {e.returncode}):\n"
                f"STDOUT: {e.stdout[-2000:] if e.stdout else '(empty)'}\n"
                f"STDERR: {e.stderr[-2000:] if e.stderr else '(empty)'}"
            ) from e

    def run_dense_reconstruction(
        self,
        sfm_scene_dir: Path,
        output_dir: Path,
        on_step: Optional[Callable[[str, object], None]] = None,
    ) -> Path:
        """
        Run OpenMVS dense pipeline on the scene.mvs produced by OpenMVG.
        Returns path to the textured OBJ file.
        """
        if not self.is_configured:
            raise RuntimeError(
                "OpenMVS is not configured. Set OPENMVS_BIN_DIR to your install/bin path."
            )

        mvs_file = sfm_scene_dir / "scene.mvs"
        if not mvs_file.exists():
            raise FileNotFoundError(f"OpenMVS scene file not found: {mvs_file}")

        from app.schemas.pipeline import StepStatus

        def mark(key: str, s: object) -> None:
            if on_step:
                on_step(key, s)

        output_dir.mkdir(parents=True, exist_ok=True)

        # All OpenMVS steps must run inside sfm_scene_dir because scene.mvs
        # stores image paths relative to that directory.
        work_dir = sfm_scene_dir

        mark("densify", StepStatus.RUNNING)
        self._run([
            str(self._binary("DensifyPointCloud")), "scene.mvs",
            "--resolution-level", "1",  # 1 = half resolution — level 0 (3060×4080) OOMs on macOS
            "--fusion-mode", "0",       # 0 = depth-map fusion (default, most robust)
            "--number-views-fuse", "2", # fuse depth maps seen by at least 2 views (more points)
        ], cwd=work_dir)
        mark("densify", StepStatus.DONE)

        mark("mesh", StepStatus.RUNNING)
        # ReconstructMesh outputs scene_dense_mesh.ply (no .mvs output in this build)
        self._run([
            str(self._binary("ReconstructMesh")), "scene_dense.mvs",
            "--decimate", "1",          # 1 = keep all faces (0 would remove all)
            "--remove-spurious", "30",  # aggressively remove floating fragments
            "--smooth", "5",            # smooth spiky artifacts from reflective surfaces
            "--close-holes", "10",      # fill gaps — 30 takes 80+ mins; 10 is fast enough
        ], cwd=work_dir)
        mark("mesh", StepStatus.DONE)

        mark("texture", StepStatus.RUNNING)
        # TextureMesh takes the original scene file + explicit mesh PLY + OBJ export
        self._run([
            str(self._binary("TextureMesh")), "scene_dense.mvs",
            "--mesh-file", "scene_dense_mesh.ply",
            "--export-type", "obj",
            "--global-seam-leveling", "1",  # blend colour seams between texture patches
        ], cwd=work_dir)
        mark("texture", StepStatus.DONE)

        mark("convert", StepStatus.RUNNING)
        obj_file = work_dir / "scene_dense_texture.obj"
        glb_file = output_dir / "scene.glb"
        obj2gltf = Path.home() / ".npm-global" / "bin" / "obj2gltf"
        subprocess.run(
            [str(obj2gltf), "-i", str(obj_file), "-o", str(glb_file)],
            check=True, capture_output=True, text=True,
        )
        mark("convert", StepStatus.DONE)

        return glb_file

    def run_command(self, tool: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = [str(self._binary(tool)), *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
