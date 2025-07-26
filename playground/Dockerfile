# Base image with ROCm support
FROM rocm/vllm-dev:base_main_20250312
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y git curl && apt-get clean

# Clone vLLM repository
RUN git clone https://github.com/vllm-project/vllm.git
WORKDIR /workspace/vllm

# Upgrade pip and install AMD/vLLM dependencies
RUN pip install --upgrade pip
# Install vLLM from source, adjust for your GPU arch
ENV VLLM_USE_PRECOMPILED=1
RUN pip install --editable .

# Install the latest Transformers version that supports Gemma 3n
RUN pip install git+https://github.com/huggingface/transformers@main # or a specific Gemma 3n branch if provided by HF