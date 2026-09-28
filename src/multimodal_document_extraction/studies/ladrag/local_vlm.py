"""Local Hugging Face transformers VisionModel for LAD-RAG† ingestion (CP-4.3B; D-019 [SUBSTITUTED] S1).

Runs an image-text-to-text model (e.g. Qwen3.5-2B, Qwen3-VL-2B-Instruct) on the local GPU in fp16
(Turing has no native bf16). Greedy decoding for temperature 0 (paper). The ``model_id`` includes the
repository, revision and settings that change outputs, so caches/fingerprints never mix settings.
Requires the optional ``vlm`` extra (torch, torchvision, pillow, transformers); model weights must be
downloaded beforehand (pinned revision).
"""

import io
import time
from dataclasses import dataclass

from multimodal_document_extraction.studies.ladrag.models import GenerationRequest, ModelReply


@dataclass(frozen=True)
class LocalVLMSpec:
    repo_id: str
    revision: str
    dtype: str = "float16"
    disable_thinking: bool = True  # Qwen3.5 thinks by default; LAD-RAG needs direct JSON
    attn_implementation: str = "sdpa"

    @property
    def model_id(self) -> str:
        flags = [self.dtype, "nothink" if self.disable_thinking else "think"]
        return f"{self.repo_id}@{self.revision[:8]}+{'+'.join(flags)}"


QWEN35_2B = LocalVLMSpec("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc")
QWEN3VL_2B = LocalVLMSpec("Qwen/Qwen3-VL-2B-Instruct", "89644892e4d85e24eaac8bacfd4f463576704203")
LOCAL_VLMS = {"qwen3.5-2b": QWEN35_2B, "qwen3-vl-2b": QWEN3VL_2B}


class TransformersVisionModel:
    """VisionModel backed by ``AutoModelForImageTextToText`` (weights loaded once)."""

    def __init__(
        self, spec: LocalVLMSpec, device: str = "cuda", local_files_only: bool = True
    ) -> None:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.spec = spec
        self.model_id = spec.model_id
        self.device = device
        self._torch = torch
        dtype = getattr(torch, spec.dtype)
        kwargs = {"revision": spec.revision, "local_files_only": local_files_only}
        started = time.perf_counter()
        self.processor = AutoProcessor.from_pretrained(spec.repo_id, **kwargs)
        self.model = (
            AutoModelForImageTextToText.from_pretrained(
                spec.repo_id, dtype=dtype, attn_implementation=spec.attn_implementation, **kwargs
            )
            .to(device)
            .eval()
        )
        self.load_seconds = time.perf_counter() - started

    def generate(self, request: GenerationRequest) -> ModelReply:
        from PIL import Image

        torch = self._torch
        images = [Image.open(io.BytesIO(image.png)).convert("RGB") for image in request.images]
        content = [{"type": "image"} for _ in images] + [{"type": "text", "text": request.prompt}]
        messages = [{"role": "user", "content": content}]
        template_kwargs = {"enable_thinking": False} if self.spec.disable_thinking else {}
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, **template_kwargs
        )
        inputs = self.processor(text=[text], images=images or None, return_tensors="pt").to(
            self.device
        )
        greedy = request.params.temperature == 0
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=request.params.max_output_tokens,
                do_sample=not greedy,
                **({} if greedy else {"temperature": request.params.temperature}),
            )
        generated = output[0, inputs["input_ids"].shape[1] :]
        reply_text = self.processor.decode(generated, skip_special_tokens=True)
        return ModelReply(
            text=reply_text,
            model_id=self.model_id,
            usage={
                "prompt_tokens": int(inputs["input_ids"].shape[1]),
                "completion_tokens": int(generated.shape[0]),
            },
            latency_s=time.perf_counter() - started,
        )
