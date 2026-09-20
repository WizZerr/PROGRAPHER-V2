from pathlib import Path

from app.datasets.xmp_reader import read_xmp


def test_missing_values_stay_missing_and_real_zero_stays_zero(
    tmp_path: Path,
) -> None:
    xmp = tmp_path / "IMG_0001.xmp"
    xmp.write_text(
        """<?xml version="1.0"?>
        <x:xmpmeta xmlns:x="adobe:ns:meta/"
          xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
          xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
          <rdf:RDF>
            <rdf:Description
              crs:Exposure2012="0"
              crs:Tint="0"
              crs:ProcessVersion="11.0"
              crs:CameraProfile="Adobe Color" />
          </rdf:RDF>
        </x:xmpmeta>
        """,
        encoding="utf-8",
    )

    result = read_xmp(xmp)

    assert result.recipe.exposure == 0.0
    assert result.recipe.tint == 0
    assert result.recipe.temperature is None
    assert result.recipe.blacks is None
    assert result.recipe.process_version == "11.0"
    assert result.recipe.camera_profile == "Adobe Color"
