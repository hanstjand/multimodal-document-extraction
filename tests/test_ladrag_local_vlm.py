import pytest

from multimodal_document_extraction.studies.ladrag.local_vlm import (
    LOCAL_VLMS,
    LocalVLMSpec,
    TransformersVisionModel,
)
from multimodal_document_extraction.studies.ladrag.models import (
    TASK_GRAPH_CONSTRUCTION,
    GenerationParams,
    GenerationRequest,
    ResourceExhaustedError,
)


def test_local_vlm_specs_are_pinned_and_ids_encode_settings():
    assert set(LOCAL_VLMS) == {"qwen3.5-2b", "qwen3-vl-2b"}
    for spec in LOCAL_VLMS.values():
        assert len(spec.revision) == 40
        assert spec.dtype == "float16"  # Turing GPU: no native bf16
        assert spec.model_id.startswith(f"{spec.repo_id}@{spec.revision[:8]}+float16+")
    think = LocalVLMSpec("x/y", "a" * 40, disable_thinking=False)
    assert think.model_id != LocalVLMSpec("x/y", "a" * 40).model_id  # settings change cache keys


def test_cuda_oom_becomes_resource_exhausted_error():
    torch = pytest.importorskip("torch")
    model = object.__new__(TransformersVisionModel)  # no weights loaded
    model._torch = torch

    def oom(request):
        raise torch.OutOfMemoryError("CUDA out of memory. Tried to allocate 1.00 GiB")

    model._generate = oom
    request = GenerationRequest(TASK_GRAPH_CONSTRUCTION, "prompt", (), GenerationParams())
    with pytest.raises(ResourceExhaustedError) as info:
        model.generate(request)
    details = info.value.details
    assert details["task"] == TASK_GRAPH_CONSTRUCTION
    assert details["error"].startswith("CUDA out of memory")
    assert details["max_output_tokens"] == 8192 and details["images"] == []
    assert "cuda_before_cleanup" in details and "cuda_after_cleanup" in details
