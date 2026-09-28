from multimodal_document_extraction.studies.ladrag.local_vlm import LOCAL_VLMS, LocalVLMSpec


def test_local_vlm_specs_are_pinned_and_ids_encode_settings():
    assert set(LOCAL_VLMS) == {"qwen3.5-2b", "qwen3-vl-2b"}
    for spec in LOCAL_VLMS.values():
        assert len(spec.revision) == 40
        assert spec.dtype == "float16"  # Turing GPU: no native bf16
        assert spec.model_id.startswith(f"{spec.repo_id}@{spec.revision[:8]}+float16+")
    think = LocalVLMSpec("x/y", "a" * 40, disable_thinking=False)
    assert think.model_id != LocalVLMSpec("x/y", "a" * 40).model_id  # settings change cache keys
