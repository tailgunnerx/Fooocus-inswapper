import os
import ssl
import sys

print('[System ARGV] ' + str(sys.argv))

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root)
os.chdir(root)

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
if "GRADIO_SERVER_PORT" not in os.environ:
    os.environ["GRADIO_SERVER_PORT"] = "7865"

ssl._create_default_https_context = ssl._create_unverified_context

import platform
import fooocus_version

from build_launcher import build_launcher
from modules.launch_util import is_installed, run, python, run_pip, requirements_met, delete_folder_content
from modules.model_loader import load_file_from_url

REINSTALL_ALL = False
TRY_INSTALL_XFORMERS = False
is_startup = True



def prepare_environment():
    # torch_index_url = os.environ.get('TORCH_INDEX_URL', "https://download.pytorch.org/whl/cu121")
    # torch_command = os.environ.get('TORCH_COMMAND',
    #                                f"pip install torch==2.1.0 torchvision==0.16.0 --extra-index-url {torch_index_url}")
    # requirements_file = os.environ.get('REQS_FILE', "requirements_versions.txt")

    print(f"Python {sys.version}")
    print(f"Fooocus version: {fooocus_version.version}")

    # if REINSTALL_ALL or not is_installed("torch") or not is_installed("torchvision"):
    #     run(f'"{python}" -m {torch_command}', "Installing torch and torchvision", "Couldn't install torch", live=True)

    if TRY_INSTALL_XFORMERS:
        if REINSTALL_ALL or not is_installed("xformers"):
            xformers_package = os.environ.get('XFORMERS_PACKAGE', 'xformers==0.0.23')
            if platform.system() == "Windows":
                if platform.python_version().startswith("3.10"):
                    run_pip(f"install -U -I --no-deps {xformers_package}", "xformers", live=True)
                else:
                    print("Installation of xformers is not supported in this version of Python.")
                    print(
                        "You can also check this and build manually: https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Xformers#building-xformers-on-windows-by-duckness")
                    if not is_installed("xformers"):
                        exit(0)
            elif platform.system() == "Linux":
                run_pip(f"install -U -I --no-deps {xformers_package}", "xformers")

    # if REINSTALL_ALL or not requirements_met(requirements_file):
    #     run_pip(f"install -r \"{requirements_file}\"", "requirements")

    return


vae_approx_filenames = [
    ('xlvaeapp.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/xlvaeapp.pth'),
    ('vaeapp_sd15.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/vaeapp_sd15.pt'),
    ('xl-to-v1_interposer-v4.0.safetensors',
     'https://huggingface.co/mashb1t/misc/resolve/main/xl-to-v1_interposer-v4.0.safetensors')
]


def ini_args():
    from args_manager import args
    return args


prepare_environment()
build_launcher()
args = ini_args()

if args.gpu_device_id is not None:
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu_device_id)
    print("Set device to:", args.gpu_device_id)

if args.hf_mirror is not None : 
    os.environ['HF_MIRROR'] = str(args.hf_mirror)
    print("Set hf_mirror to:", args.hf_mirror)

from modules import config
from modules.hash_cache import init_cache
os.environ["U2NET_HOME"] = config.path_inpaint

os.environ['GRADIO_TEMP_DIR'] = config.temp_path

if config.temp_path_cleanup_on_launch:
    print(f'[Cleanup] Attempting to delete content of temp dir {config.temp_path}')
    result = delete_folder_content(config.temp_path, '[Cleanup] ')
    if result:
        print("[Cleanup] Cleanup successful")
    else:
        print(f"[Cleanup] Failed to delete content of temp dir.")


def download_models(default_model, previous_default_models, checkpoint_downloads, embeddings_downloads, lora_downloads, vae_downloads):
    global is_startup

    for file_name, url in vae_approx_filenames:
        load_file_from_url(url=url, model_dir=config.path_vae_approx, file_name=file_name)

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_expansion.bin',
        model_dir=config.path_fooocus_expansion,
        file_name='pytorch_model.bin'
    )

    if args.disable_preset_download:
        print('Skipped model download.')
        return default_model, checkpoint_downloads

    # For each model listed as a preset download, check if it already exists
    # or if an alternative is available. If not, ask the user before downloading.
    models_to_skip = []

    for model_name in list(checkpoint_downloads.keys()):
        model_exists = False
        for path in config.paths_checkpoints:
            if os.path.exists(os.path.join(path, model_name)):
                model_exists = True
                break

        if model_exists:
            continue

        # Check if an alternative model exists (either from previous_default_models or any model in checkpoints)
        alternative_found = False
        if not args.always_download_new_model:
            # First check previous_default_models list
            for alternative_model_name in previous_default_models:
                if alternative_model_name == model_name:
                    continue  # skip self
                for path in config.paths_checkpoints:
                    if os.path.exists(os.path.join(path, alternative_model_name)):
                        print(f'You do not have [{model_name}] but you have [{alternative_model_name}].')
                        print(f'Fooocus will use [{alternative_model_name}] to avoid downloading new models.')
                        models_to_skip.append(model_name)
                        if default_model == model_name:
                            default_model = alternative_model_name
                        alternative_found = True
                        break
                if alternative_found:
                    break

            # If no previous default model match, check if ANY model exists in checkpoints folder
            if not alternative_found:
                available_models = config.get_model_filenames(config.paths_checkpoints)
                if available_models:
                    alt_model = available_models[0]
                    print(f'Default model [{model_name}] not found, but found [{alt_model}] in checkpoints folder.')
                    print(f'Fooocus will use [{alt_model}] to avoid downloading new models.')
                    models_to_skip.append(model_name)
                    if default_model == model_name:
                        default_model = alt_model
                    alternative_found = True

        if not alternative_found:
            # No models found at all in checkpoints folder — ask user if they want to download
            if is_startup:
                try:
                    user_input = input(f"Model [{model_name}] not found. Do you want to download it? [y/N]: ").strip().lower()
                except Exception:
                    user_input = 'n'
            else:
                user_input = 'n'

            if user_input in ['y', 'yes']:
                print(f"Downloading [{model_name}]...")
            else:
                print(f"Skipping download of [{model_name}].")
                models_to_skip.append(model_name)
                if default_model == model_name:
                    default_model = ""
                print("WARNING: No models found in the checkpoints folder! The app will start up, but you must place a model in models/checkpoints.")

    # Remove skipped models from download queue
    checkpoint_downloads = {k: v for k, v in checkpoint_downloads.items() if k not in models_to_skip}

    for file_name, url in checkpoint_downloads.items():
        load_file_from_url(url=url, model_dir=config.paths_checkpoints[0], file_name=file_name)
    for file_name, url in embeddings_downloads.items():
        load_file_from_url(url=url, model_dir=config.path_embeddings, file_name=file_name)
    for file_name, url in lora_downloads.items():
        load_file_from_url(url=url, model_dir=config.paths_loras[0], file_name=file_name)
    for file_name, url in vae_downloads.items():
        load_file_from_url(url=url, model_dir=config.path_vae, file_name=file_name)

    return default_model, checkpoint_downloads



config.default_base_model_name, config.checkpoint_downloads = download_models(
    config.default_base_model_name, config.previous_default_models, config.checkpoint_downloads,
    config.embeddings_downloads, config.lora_downloads, config.vae_downloads)

config.update_files()
init_cache(config.model_filenames, config.paths_checkpoints, config.lora_filenames, config.paths_loras)

is_startup = False
from webui import *

