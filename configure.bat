@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  Fooocus-inswapper Windows Setup
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: Step 0 — Verify prerequisites
:: ---------------------------------------------------------------
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed or not on PATH.
    echo         Download it from: https://git-scm.com/download/win
    pause & exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download Python 3.10 from: https://www.python.org/downloads/release/python-31011/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause & exit /b 1
)

:: Verify Python version is 3.10.x (required for compatibility)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo [Info] Python version: %PYVER%
echo %PYVER% | findstr /r "^3\.10\." >nul
if errorlevel 1 (
    echo [WARNING] Python 3.10 is strongly recommended. You have %PYVER%.
    echo           Continuing anyway, but some packages may fail.
    echo.
    timeout /t 5 >nul
)

:: ---------------------------------------------------------------
:: Step 1 — Git LFS + clone CodeFormer into inswapper folder
:: ---------------------------------------------------------------
echo [Step 1] Installing Git LFS and cloning CodeFormer...
git lfs install
if not exist "inswapper\CodeFormer" (
    cd inswapper
    git clone https://huggingface.co/spaces/sczhou/CodeFormer
    cd ..
) else (
    echo [Info] CodeFormer already cloned, skipping.
)

:: ---------------------------------------------------------------
:: Step 2 — Create Python virtual environment
:: ---------------------------------------------------------------
echo.
echo [Step 2] Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
) else (
    echo [Info] venv already exists, skipping.
)

call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause & exit /b 1
)

:: Upgrade pip to avoid old pip resolver issues
python -m pip install --upgrade pip --quiet

:: ---------------------------------------------------------------
:: Step 3 — Install PyTorch with CUDA 11.8
::          cu118 wheels support: GTX 10xx, 20xx, 30xx, 40xx
::          (Note: for CUDA 12.x use --index-url .../whl/cu121)
:: ---------------------------------------------------------------
echo.
echo [Step 3] Installing PyTorch 2.1.0 with CUDA 11.8 support...
echo          (Supports GTX 10xx / 20xx / 30xx / 40xx series)
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 ^
    --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed. Check your internet connection.
    pause & exit /b 1
)

:: Quick sanity-check that CUDA is visible
echo.
echo [Info] Verifying CUDA availability...
python -c "import torch; print('[CUDA] Available:', torch.cuda.is_available()); print('[CUDA] Device count:', torch.cuda.device_count()); print('[CUDA] Device name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

:: ---------------------------------------------------------------
:: Step 4 — Install project requirements
:: ---------------------------------------------------------------
echo.
echo [Step 4] Installing project requirements...
pip install -r requirements_versions.txt
if errorlevel 1 (
    echo [ERROR] Requirements installation failed. See output above.
    pause & exit /b 1
)

:: ---------------------------------------------------------------
:: Step 5 — Copy CodeFormer packages into venv
:: ---------------------------------------------------------------
echo.
echo [Step 5] Copying CodeFormer packages into virtualenv...
if exist "inswapper\CodeFormer\CodeFormer\basicsr" (
    xcopy /E /I /Y "inswapper\CodeFormer\CodeFormer\basicsr" "venv\Lib\site-packages\basicsr"
) else (
    echo [WARNING] basicsr source not found — CodeFormer may not have cloned correctly.
)
if exist "inswapper\CodeFormer\CodeFormer\facelib" (
    xcopy /E /I /Y "inswapper\CodeFormer\CodeFormer\facelib" "venv\Lib\site-packages\facelib"
) else (
    echo [WARNING] facelib source not found — CodeFormer may not have cloned correctly.
)

:: ---------------------------------------------------------------
:: Step 6 — Download inswapper_128.onnx model
:: ---------------------------------------------------------------
echo.
echo [Step 6] Downloading inswapper_128.onnx model...
if not exist "inswapper\checkpoints" mkdir "inswapper\checkpoints"
if not exist "inswapper\checkpoints\inswapper_128.onnx" (
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri 'https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx' -OutFile '.\inswapper\checkpoints\inswapper_128.onnx'"
    if not exist "inswapper\checkpoints\inswapper_128.onnx" (
        echo [WARNING] inswapper_128.onnx download failed. You may need to download it manually.
    )
) else (
    echo [Info] inswapper_128.onnx already exists, skipping.
)

:: ---------------------------------------------------------------
:: Step 7 — Download and extract antelopev2 models for InstantID
:: ---------------------------------------------------------------
echo.
echo [Step 7] Setting up InstantID antelopev2 models...
if not exist "InstantID\models\antelopev2" mkdir "InstantID\models\antelopev2"

:: Check if models already extracted
if not exist "InstantID\models\antelopev2\1k3d68.onnx" (
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri 'https://keeper.mpdl.mpg.de/f/2d58b7fed5a74cb5be83/?dl=1' -OutFile '.\InstantID\models\antelopev2.zip' -TimeoutSec 120"
    if exist "InstantID\models\antelopev2.zip" (
        powershell -NoProfile -Command ^
            "Expand-Archive -Path '.\InstantID\models\antelopev2.zip' -DestinationPath '.\InstantID\models\antelopev2' -Force"
        del /f /q "InstantID\models\antelopev2.zip"
    ) else (
        echo [WARNING] antelopev2.zip download failed. InstantID face analysis may not work.
        echo           You can manually place the models in InstantID\models\antelopev2\
    )
) else (
    echo [Info] antelopev2 models already present, skipping.
)

:: ---------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------
echo.
echo ============================================================
echo  Setup complete!
echo  Run the application with:  run.bat
echo ============================================================
pause