"""Source separation using Demucs (optional dependency)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StemPaths(BaseModel):
    """Paths to separated audio stems."""

    vocals: str = ""
    drums: str = ""
    bass: str = ""
    other: str = ""
    available: bool = False


def _unsafe_cache_reason(cache_dir: Path) -> str | None:
    """Return why cache_dir must not hold stems, or None if it is fine."""
    from xlights_mcp.config import load_config

    resolved = cache_dir.expanduser().resolve()
    home = Path.home()
    blocked = [home / "My Drive", home / "Library" / "CloudStorage"]
    blocked += [Path(p).expanduser() for p in load_config().show_folders.values()]
    for root in blocked:
        if resolved.is_relative_to(root.resolve()):
            return f"cache_dir {resolved} is inside {root}"
    return None


def stem_dir_for(audio_path: Path, cache_dir: Path) -> Path:
    """Per-song stem folder under cache_dir; never beside the audio file."""
    digest = hashlib.sha1(str(audio_path.resolve()).encode()).hexdigest()[:8]
    return cache_dir.expanduser() / f"{audio_path.stem}-{digest}"


def separate_stems(
    audio_path: Path,
    output_dir: Path | None = None,
    model: str = "htdemucs",
    cache_dir: Path | None = None,
) -> StemPaths:
    """Separate audio into stems using Demucs.

    Requires the 'separation' optional dependency:
        pip install xlights-mcp-server[separation]

    Args:
        audio_path: Path to audio file
        output_dir: Where to save stems (defaults to a folder under cache_dir)
        cache_dir: Stem cache root (defaults to audio.cache_dir from config)
        model: Demucs model name
    """
    try:
        import torch
        import demucs.separate
    except ImportError:
        logger.warning(
            "Demucs not installed. Install with: pip install xlights-mcp-server[separation]"
        )
        return StemPaths(available=False)

    if cache_dir is None:
        from xlights_mcp.config import load_config

        cache_dir = load_config().audio.cache_dir
    reason = _unsafe_cache_reason(output_dir.parent if output_dir else cache_dir)
    if reason:
        logger.error(f"Refusing to write stems: {reason}")
        return StemPaths(available=False)
    if output_dir is None:
        output_dir = stem_dir_for(audio_path, cache_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check cache — vocals is the minimum required stem
    stems = StemPaths(available=True)
    expected = {
        "vocals": output_dir / "vocals.wav",
        "drums": output_dir / "drums.wav",
        "bass": output_dir / "bass.wav",
        "other": output_dir / "other.wav",
    }

    vocals_cached = expected["vocals"].exists()
    if vocals_cached:
        logger.info("Using cached stems")
        stems.vocals = str(expected["vocals"])
        for name in ("drums", "bass", "other"):
            if expected[name].exists():
                setattr(stems, name, str(expected[name]))
        return stems

    logger.info(f"Separating stems with {model}: {audio_path}")

    try:
        # Fix SSL cert issues on macOS
        import os
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
        except ImportError:
            pass

        # Try newer demucs.api first, fall back to CLI-based separation
        try:
            import demucs.api
            separator = demucs.api.Separator(model=model)
            _, outputs = separator.separate_audio_file(str(audio_path))

            import soundfile as sf
            for stem_name, tensor in outputs.items():
                out_path = output_dir / f"{stem_name}.wav"
                audio_np = tensor.cpu().numpy()
                if audio_np.ndim > 1:
                    audio_np = audio_np.T
                sf.write(str(out_path), audio_np, separator.samplerate)
                setattr(stems, stem_name, str(out_path))
        except (ImportError, AttributeError):
            # Older demucs — use CLI-style separation
            import subprocess
            import sys
            result = subprocess.run(
                [sys.executable, "-m", "demucs.separate",
                 "-n", model,
                 "-o", str(output_dir.parent),
                 str(audio_path)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"demucs failed: {result.stderr[-1000:]}")

            # Demucs CLI outputs to: output_dir.parent / model / audio_stem / *.wav
            cli_out = output_dir.parent / model / audio_path.stem
            import shutil
            for stem_name in ("vocals", "drums", "bass", "other"):
                src = cli_out / f"{stem_name}.wav"
                if src.exists():
                    dst = expected[stem_name]
                    shutil.move(str(src), str(dst))
                    setattr(stems, stem_name, str(dst))

        logger.info(f"Stems saved to {output_dir}")
    except Exception as e:
        logger.error(f"Stem separation failed: {e}")
        stems.available = False

    return stems
