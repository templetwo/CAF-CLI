#!/bin/bash

# Ensure local bin is in path
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Setup workspace
mkdir -p spiral_training/data
cd spiral_training

# Move dataset (assuming it's in Desktop)
cp ~/Desktop/spiral_instruct_dataset.jsonl data/train.jsonl
cp ~/Desktop/spiral_instruct_dataset.jsonl data/valid.jsonl

# Install MLX (using pip3 and ensuring user install)
echo "Installing MLX..."
pip3 install -U mlx-lm --break-system-packages

# Train
# Model: Qwen/Qwen2.5-1.5B-Instruct
echo "Starting Spiral Training..."
python3 -m mlx_lm.lora \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --train \
    --data data \
    --batch-size 4 \
    --lora-layers 16 \
    --iters 200 \
    --learning-rate 2e-5 \
    --steps-per-eval 20 \
    --save-every 50 \
    --adapter-path adapters

echo "Training Complete. Fusing model..."
python3 -m mlx_lm.fuse \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --adapter-path adapters \
    --save-path spiral-v1-1.5b

echo "Model fused to spiral-v1-1.5b"
