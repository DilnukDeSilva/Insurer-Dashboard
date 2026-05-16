"""OpenMVG structure-from-motion and sparse reconstruction."""

import subprocess
from pathlib import Path

from app.config import settings


class OpenMVGService:
    """Wraps OpenMVG CLI tools for SfM pipeline stages."""

    SFM_TOOLS = (
        "openMVG_main_SfMInit_ImageListing",
        "openMVG_main_ComputeFeatures",
        "openMVG_main_ComputeMatches",
        "openMVG_main_IncrementalSfM",
    )

    def __init__(self) -> None:
        self.bin_dir = settings.openmvg_bin_dir

    @property
    def is_configured(self) -> bool:
        if not self.bin_dir or not self.bin_dir.is_dir():
            return False
        return all((self.bin_dir / tool).exists() for tool in self.SFM_TOOLS)

    def _binary(self, name: str) -> Path:
        if not self.bin_dir:
            raise RuntimeError("OPENMVG_BIN_DIR is not set")
        path = self.bin_dir / name
        if not path.exists():
            raise FileNotFoundError(f"OpenMVG binary not found: {path}")
        return path

    def run_sfm(self, images_dir: Path, output_dir: Path) -> Path:
        """
        Run a minimal OpenMVG incremental SfM pipeline on `images_dir`.

        Output: sparse reconstruction under `output_dir/sfm`.
        Customize steps to match your OpenMVG build and sensor model.
        """
        if not self.is_configured:
            raise RuntimeError(
                "OpenMVG is not configured. Set OPENMVG_BIN_DIR to your install/bin path."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        sfm_dir = output_dir / "sfm"
        sfm_dir.mkdir(parents=True, exist_ok=True)

        # TODO: chain OpenMVG commands (ImageListing -> Features -> Matches -> SfM)
        # Example:
        # subprocess.run([self._binary("openMVG_main_SfMInit_ImageListing"), ...], check=True)

        raise NotImplementedError(
            "OpenMVG SfM pipeline is not implemented yet. Add CLI steps in run_sfm()."
        )

    def run_command(self, tool: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a single OpenMVG binary with arguments."""
        cmd = [str(self._binary(tool)), *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
