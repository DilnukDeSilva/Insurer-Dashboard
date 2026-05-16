"""OpenMVS dense reconstruction from OpenMVG output."""

import subprocess
from pathlib import Path

from app.config import settings


class OpenMVSService:
    """Wraps OpenMVS CLI tools for dense point cloud and mesh generation."""

    DENSE_TOOLS = (
        "InterfaceVisualSFM",
        "DensifyPointCloud",
        "ReconstructMesh",
        "RefineMesh",
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

    def run_dense_reconstruction(self, sfm_scene_dir: Path, output_dir: Path) -> Path:
        """
        Convert OpenMVG output and run OpenMVS densify + mesh pipeline.

        Input: directory containing OpenMVG reconstruction (or exported scene)
        Output: dense point cloud / mesh under `output_dir/mvs`
        """
        if not self.is_configured:
            raise RuntimeError(
                "OpenMVS is not configured. Set OPENMVS_BIN_DIR to your install/bin path."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        mvs_dir = output_dir / "mvs"
        mvs_dir.mkdir(parents=True, exist_ok=True)

        # TODO: InterfaceVisualSFM -> DensifyPointCloud -> ReconstructMesh -> ...
        raise NotImplementedError(
            "OpenMVS dense pipeline is not implemented yet. Add CLI steps in run_dense_reconstruction()."
        )

    def run_command(self, tool: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = [str(self._binary(tool)), *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
