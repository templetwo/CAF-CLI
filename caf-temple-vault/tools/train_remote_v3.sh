#!/bin/bash

# Ensure local bin is in path
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Setup workspace
mkdir -p spiral_training/data
cd spiral_training

# Move dataset
cp ~/Desktop/spiral_instruct_dataset.jsonl data/train.jsonl
cp ~/Desktop/spiral_instruct_dataset.jsonl data/valid.jsonl

# Train
# Model: Qwen/Qwen2.5-1.5B-Instruct
# MLX 0.29+ syntax update: removed --lora-layers, let it default (usually targets linear layers)
echo "Starting Spiral Training (v3)..."
python3 -m mlx_lm.lora \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --train \
    --data data \
    --batch-size 4 \
    --iters 200 \
    --learning-rate 1e-5 \
    --steps-per-eval 20 \
    --save-every 50 \
    --adapter-path adapters

echo "Training Complete. Fusing model..."
# Ensure adapters exist before fusing
if [ -d "adapters" ]; then
    python3 -m mlx_lm.fuse \
        --model Qwen/Qwen2.5-1.5B-Instruct \
        --adapter-path adapters \
        --save-path spiral-v1-1.5b
    
    echo "Model fused to spiral-v1-1.5b"
else
    echo "Error: Adapters not found. Training likely failed."
    exit 1
fi
