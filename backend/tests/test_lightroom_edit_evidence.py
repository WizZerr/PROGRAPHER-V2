from app.datasets.contracts import SourceIdentity, TargetRecipe
from app.lightroom_bridge.contracts import LightroomEditEvidence


def test_virtual_copy_identity_is_explicit_not_inferred() -> None:
    source = SourceIdentity(
        absolute_path="C:/photo.CR3",
        relative_path="photo.CR3",
        filename="photo.CR3",
        extension=".CR3",
        size_bytes=1,
        modified_ns=1,
        fingerprint="abc",
    )

    evidence = LightroomEditEvidence(
        kind="virtual_copy",
        source_identity=source,
        catalog_path="C:/catalog.lrcat",
        lightroom_image_id="123",
        virtual_copy_id="456",
        virtual_copy_name="Color Final",
        target_recipe=TargetRecipe(
            exposure=0.0,
            temperature=5000,
            tint=0,
            blacks=-40.0,
            process_version="11.0",
            camera_profile="Adobe Color",
        ),
        verification_method="lightroom_catalog_or_plugin",
        verified_final=True,
    )

    assert evidence.kind == "virtual_copy"
    assert evidence.virtual_copy_id == "456"
    assert evidence.verified_final is True
