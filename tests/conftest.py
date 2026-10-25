from pathlib import Path

import pytest
import yaml

from kiddy.settings import Settings
from kiddy.studio import RunContext

CONFIG = Path(__file__).resolve().parents[1] / "config" / "channel.yaml"


@pytest.fixture
def fake_ctx(tmp_path: Path) -> RunContext:
    """A fake, offline run that writes everything under the test's temp folder."""
    config = yaml.safe_load(CONFIG.read_text("utf-8"))
    # Small and slow-framed: the tests check the plumbing, not the pixels. 480 wide is exactly
    # 1/4 of Remotion's 1920, so its scaled frames stay whole pixels.
    config["video"] = {"width": 480, "height": 270, "fps": 10}
    small = tmp_path / "channel.yaml"
    small.write_text(yaml.safe_dump(config), encoding="utf-8")
    return RunContext(
        fake=True,
        config_path=str(small),
        output_dir=str(tmp_path / "output"),
        data_dir=str(tmp_path / "data"),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings.load(CONFIG)
