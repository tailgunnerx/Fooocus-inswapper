import sys
import os
import numpy as np
from PIL import Image

# Ensure inswapper package is importable relative to this file's location
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_inswapper_path = os.path.join(_repo_root, 'inswapper')
if _inswapper_path not in sys.path:
    sys.path.insert(0, _inswapper_path)

from inswapper.swapper import process


def perform_face_swap(images, inswapper_source_image, inswapper_source_image_indicies, inswapper_target_image_indicies):
    """
    Perform face swap using inswapper, then apply CodeFormer face restoration.

    Args:
        images: list of PIL Images or numpy arrays (generation output)
        inswapper_source_image: numpy array of the source face image
        inswapper_source_image_indicies: list of face indices to use from source
        inswapper_target_image_indicies: list of face indices to use in target

    Returns:
        list of numpy BGR images with face swap + restoration applied
    """
    # Resolve model path relative to repo root (not relative to cwd)
    _onnx_model_path = os.path.join(_inswapper_path, 'checkpoints', 'inswapper_128.onnx')
    if not os.path.exists(_onnx_model_path):
        raise FileNotFoundError(
            f"inswapper_128.onnx not found at: {_onnx_model_path}\n"
            "Please run configure.bat to download the model."
        )

    swapped_images = []
    result_image = None

    for item in images:
        source_image = Image.fromarray(inswapper_source_image)
        print(f"Inswapper: Source indices: {inswapper_source_image_indicies}")
        print(f"Inswapper: Target indices: {inswapper_target_image_indicies}")
        result_image = process(
            [source_image],
            item,
            inswapper_source_image_indicies,
            inswapper_target_image_indicies,
            _onnx_model_path
        )

    # Bug fix: restoration was outside the loop so only the last iteration's
    # result_image was ever used. We now process result_image per iteration.
    if result_image is not None:
        try:
            from inswapper.restoration import (
                face_restoration, check_ckpts, set_realesrgan,
                torch, ARCH_REGISTRY, cv2
            )

            # Ensure CodeFormer checkpoints are downloaded
            check_ckpts()

            upsampler = set_realesrgan()

            # Device selection: prefer CUDA on Windows/Nvidia; MPS on Apple Silicon
            if torch.cuda.is_available():
                device = torch.device("cuda")
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = torch.device("mps")
            else:
                device = torch.device("cpu")
            print(f"Inswapper restoration device: {device}")

            # Resolve CodeFormer weights path relative to repo root
            ckpt_path = os.path.join(_inswapper_path, 'CodeFormer', 'CodeFormer', 'weights', 'CodeFormer', 'codeformer.pth')
            if not os.path.exists(ckpt_path):
                raise FileNotFoundError(
                    f"CodeFormer weights not found at: {ckpt_path}\n"
                    "Please run configure.bat to clone CodeFormer."
                )

            codeformer_net = ARCH_REGISTRY.get("CodeFormer")(
                dim_embd=512,
                codebook_size=1024,
                n_head=8,
                n_layers=9,
                connect_list=["32", "64", "128", "256"],
            ).to(device)

            checkpoint = torch.load(ckpt_path, map_location=device)["params_ema"]
            codeformer_net.load_state_dict(checkpoint)
            codeformer_net.eval()

            result_bgr = cv2.cvtColor(np.array(result_image), cv2.COLOR_RGB2BGR)
            result_bgr = face_restoration(
                result_bgr,
                True,
                True,
                1,
                0.5,
                upsampler,
                codeformer_net,
                device
            )
            swapped_images.append(result_bgr)

        except ImportError as e:
            print(f"[WARNING] CodeFormer restoration unavailable: {e}")
            print("[WARNING] Returning raw swap result without enhancement.")
            result_bgr = cv2.cvtColor(np.array(result_image), cv2.COLOR_RGB2BGR)
            swapped_images.append(result_bgr)

    return swapped_images
