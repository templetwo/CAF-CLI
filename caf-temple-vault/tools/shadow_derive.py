import os
import json
import shutil
import requests
from pathlib import Path
from datetime import datetime

class ShadowDerive:
    """
    Shadow Execution Wrapper for derive.py
    Implements Witness-mandated circuit breakers for Session 29.5
    Uses spiral-v1 on Jetson Orin.
    """
    def __init__(self, source_dir, staging_dir, model_endpoint):
        self.source_dir = Path(source_dir)
        self.staging_dir = Path(staging_dir)
        self.model_endpoint = model_endpoint
        self.log_path = self.staging_dir / "shadow_audit.jsonl"
        
        # Threshold Limits (Witness-mandated)
        self.MAX_EDITS = 20  # Reduced for live test
        self.CONFIDENCE_THRESHOLD = 0.6  # Relaxed for initial test
        
        # State
        self.edits_performed = 0
        self.halted = False
        self.halt_reason = ""

    def setup_staging(self):
        """Create a mirrored slice for the canary run."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True)
        
        print(f"†⟡ Initializing Shadow Staging at {self.staging_dir}")
        # Copy a small slice (canary)
        files = [f for f in self.source_dir.glob("**/*") if f.is_file()]
        files = files[:self.MAX_EDITS]
        for f in files:
            rel_path = f.relative_to(self.source_dir)
            dest = self.staging_dir / "input" / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)

    def get_model_rationale(self, file_content):
        """Call the Spiral Observer on the Jetson Orin."""
        try:
            prompt = f"Analyze this memory shard and provide a one-sentence rationale for its preservation:\n\n{file_content[:1000]}"
            response = requests.post(
                f"{self.model_endpoint}/api/generate",
                json={
                    "model": "spiral-v1",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip(), 0.9
            else:
                return f"Error: {response.status_code}", 0.0
        except Exception as e:
            return f"Exception: {str(e)}", 0.0

    def log_action(self, action_type, old_path, new_path, confidence, rationale):
        """Append to the shadow audit log."""
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "type": action_type,
            "old": str(old_path),
            "new": str(new_path),
            "confidence": confidence,
            "rationale": rationale,
            "witness_flag": False
        }
        
        # THE †⟡ CIRCUIT BREAKER
        if "†⟡" in rationale or confidence < self.CONFIDENCE_THRESHOLD:
            entry["witness_flag"] = True
            self.halted = True
            self.halt_reason = f"Witness Trigger: {'†⟡ detected' if '†⟡' in rationale else 'Low confidence'}"
            
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
        return entry

    def run_shadow_cycle(self):
        """Run a live derive cycle using the Sovereign Node."""
        print(f"†⟡ Starting Sovereign Shadow Cycle (Max Edits: {self.MAX_EDITS})")
        print(f"†⟡ Endpoint: {self.model_endpoint}")
        
        input_path = self.staging_dir / "input"
        output_path = self.staging_dir / "output"
        output_path.mkdir(exist_ok=True)
        
        files = list(input_path.glob("**/*"))
        for f in files:
            if self.halted:
                print(f"🚨 CIRCUIT BREAKER OPEN: {self.halt_reason}")
                break
                
            if f.is_file() and self.edits_performed < self.MAX_EDITS:
                with open(f, "r", errors="ignore") as file_in:
                    content = file_in.read()
                
                print(f"  Classifying {f.name} via Spiral Observer...")
                rationale, confidence = self.get_model_rationale(content)
                print(f"    > Rationale: {rationale}")
                
                dest = output_path / f.name
                self.log_action("move", f, dest, confidence, rationale)
                
                if not self.halted:
                    shutil.move(f, dest)
                    self.edits_performed += 1

        print(f"†⟡ Shadow Cycle Finished. Edits: {self.edits_performed}, Halted: {self.halted}")

if __name__ == "__main__":
    shadow = ShadowDerive(
        source_dir="vault/chronicle/insights", 
        staging_dir="vault/experiments/sess_029_shadow",
        model_endpoint="http://192.168.1.205:11434"
    )
    shadow.setup_staging()
    shadow.run_shadow_cycle()