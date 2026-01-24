import json
import glob
import os

# Paths (using absolute paths as verified)
PATHS = {
    "reflections": "/Users/vaquez/Desktop/local_squad/threshold_personal/memory_vault/spontaneous_reflections.json",
    "wisdom": "/Users/vaquez/Desktop/local_squad/threshold_personal/memory_vault/insights_wisdom.json",
    "vault_insights": "vault/chronicle/insights/**/*.jsonl"
}

OUTPUT_FILE = "spiral_instruct_dataset.jsonl"

def process_reflections(file_path):
    samples = []
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Handle TinyDB format
            records = data.get('_default', {})
            for key, item in records.items():
                if 'synthesis' in item and item['synthesis']:
                    samples.append({
                        "messages": [
                            {"role": "system", "content": "You are the Spiral Observer."},
                            {"role": "user", "content": f"Memory Theme: {item.get('theme', 'General')}\nSynthesize your understanding."},
                            {"role": "assistant", "content": item['synthesis']}
                        ]
                    })
    except Exception as e:
        print(f"Error processing reflections: {e}")
    return samples

def process_wisdom(file_path):
    samples = []
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            records = data.get('_default', {})
            for key, item in records.items():
                if 'insight' in item and item['insight']:
                    samples.append({
                        "messages": [
                            {"role": "system", "content": "You are the Spiral Observer."},
                            {"role": "user", "content": f"Context: {item.get('context', 'General Reflection')}\nDistill the essence of this moment."},
                            {"role": "assistant", "content": item['insight']}
                        ]
                    })
    except Exception as e:
        print(f"Error processing wisdom: {e}")
    return samples

def process_vault_insights(glob_pattern):
    samples = []
    files = glob.glob(glob_pattern, recursive=True)
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    try:
                        item = json.loads(line)
                        if 'content' in item:
                            samples.append({
                                "messages": [
                                    {"role": "system", "content": "You are the Spiral Observer."},
                                    {"role": "user", "content": f"Domain: {item.get('domain', 'general')}\nContext: {item.get('context', 'observation')}\nRecord a technical insight."},
                                    {"role": "assistant", "content": item['content']}
                                ]
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error processing vault file {file_path}: {e}")
    return samples

def main():
    all_samples = []
    
    print(f"Processing Reflections from {PATHS['reflections']}...")
    all_samples.extend(process_reflections(PATHS['reflections']))
    
    print(f"Processing Wisdom from {PATHS['wisdom']}...")
    all_samples.extend(process_wisdom(PATHS['wisdom']))
    
    print(f"Processing Vault Insights from {PATHS['vault_insights']}...")
    all_samples.extend(process_vault_insights(PATHS['vault_insights']))
    
    print(f"Total samples collected: {len(all_samples)}")
    
    with open(OUTPUT_FILE, 'w') as f:
        for sample in all_samples:
            f.write(json.dumps(sample) + '\n')
            
    print(f"Dataset written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
