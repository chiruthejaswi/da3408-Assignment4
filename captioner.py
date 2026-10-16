"""Model wrapper. Real BLIP on CPU by default; CAPTION_MOCK=1 gives a fake model
so you can develop the dashboard without downloading ~1GB of weights."""
import os
import random
import time

from PIL import Image

MODEL_NAME = os.getenv("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
MOCK = os.getenv("CAPTION_MOCK", "0") == "1"
MAX_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "512"))  # downscale to keep CPU latency sane


class MockCaptioner:
    name = "mock"
    device = "cpu"
    weights_bytes = 0

    def caption(self, image: Image.Image) -> str:
        time.sleep(random.uniform(0.2, 1.5))
        return random.choice(
            ["a dog running on grass", "a city street at night", "a bowl of fruit on a table"]
        )


class BlipCaptioner:
    device = "cpu"

    def __init__(self):
        import torch
        from transformers import BlipForConditionalGeneration, BlipProcessor

        self.torch = torch
        self.name = MODEL_NAME
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        self.processor = BlipProcessor.from_pretrained(MODEL_NAME)
        self.model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME).eval()
        self.weights_bytes = sum(p.numel() * p.element_size() for p in self.model.parameters())

    def caption(self, image: Image.Image) -> str:
        inputs = self.processor(images=image, return_tensors="pt")
        with self.torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=30, num_beams=3)
        return self.processor.decode(out[0], skip_special_tokens=True)


def build_captioner():
    return MockCaptioner() if MOCK else BlipCaptioner()


def prepare_image(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img
