"""Action handlers for the CAF agent."""

import glob
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Any

# Global context for vault access and action history
_vault_context: dict = {}
_action_history: list = []  # Stack of (action, argument, success, output)
_last_paths: list = []  # Paths from last FIND/EXPLORE


def set_vault_context(events: Any, session_id: str):
    """Set vault context for actions that need it."""
    global _vault_context, _action_history, _last_paths
    _vault_context = {"events": events, "session_id": session_id}
    _action_history = []
    _last_paths = []


def push_action(action: str, argument: str, success: bool, output: str):
    """Record an action to history."""
    global _action_history
    _action_history.append({
        "action": action,
        "argument": argument,
        "success": success,
        "output": output,
    })


def get_last_action() -> Optional[dict]:
    """Get the most recent action."""
    return _action_history[-1] if _action_history else None


def resolve_path(path: str) -> str:
    """Resolve path references like $0, $1, $LAST, $STASH."""
    global _last_paths, _cache
    if path.startswith("$"):
        if path == "$LAST" and _last_paths:
            return _last_paths[0]
        if path == "$STASH" and "$STASH" in _cache:
            return _cache["$STASH"]
        try:
            idx = int(path[1:])
            if 0 <= idx < len(_last_paths):
                return _last_paths[idx]
        except ValueError:
            # Check cache for named reference
            key = path[1:]
            if key in _cache:
                return _cache[key]
    return path


def handle_read(filepath: str) -> Tuple[bool, str]:
    """Read a file and return its contents. Supports $0, $1, $LAST for path refs."""
    resolved = resolve_path(filepath)
    try:
        path = Path(resolved).expanduser()
        if not path.exists():
            return False, f"File not found: {resolved}"
        content = path.read_text()
        # Show full content for small files, truncate large ones
        if len(content) <= 8000:
            return True, f"Contents of {resolved}:\n{content}"
        return True, f"Contents of {resolved} (truncated):\n{content[:8000]}"
    except Exception as e:
        return False, f"Error reading {resolved}: {e}"


def handle_shell(command: str) -> Tuple[bool, str]:
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout or result.stderr
        if result.returncode != 0:
            return False, f"Command failed: {output[:1000]}"
        return True, output[:1000] if output else "Command completed successfully"
    except subprocess.TimeoutExpired:
        return False, "Command timed out (60s)"
    except Exception as e:
        return False, f"Error: {e}"


def handle_code(filepath: str, content: str) -> Tuple[bool, str]:
    """Write content to a file. Creates backup for UNDO."""
    try:
        path = Path(filepath).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if path.exists():
            backup = Path(filepath + ".bak")
            backup.write_text(path.read_text())

        path.write_text(content)
        return True, f"Wrote {len(content)} bytes to {filepath}"
    except Exception as e:
        return False, f"Error writing {filepath}: {e}"


def handle_edit(filepath: str, old_text: str, new_text: str) -> Tuple[bool, str]:
    """Edit a file by replacing old_text with new_text. Creates backup for UNDO."""
    resolved = resolve_path(filepath)
    try:
        path = Path(resolved).expanduser()
        if not path.exists():
            return False, f"File not found: {resolved}"

        content = path.read_text()

        # Check if old_text exists
        if old_text not in content:
            # Show nearby content for debugging
            lines = content.split('\n')[:20]
            preview = '\n'.join(lines)
            return False, f"Text not found in {resolved}. First 20 lines:\n{preview[:500]}"

        # Count occurrences
        count = content.count(old_text)
        if count > 1:
            return False, f"Ambiguous: '{old_text[:30]}...' appears {count} times. Be more specific."

        # Create backup
        backup = Path(resolved + ".bak")
        backup.write_text(content)

        # Replace and write
        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content)

        return True, f"Edited {resolved}: replaced {len(old_text)} chars with {len(new_text)} chars"
    except Exception as e:
        return False, f"Edit error: {e}"


def handle_git_add(path: str) -> Tuple[bool, str]:
    """Stage files for git commit."""
    return handle_shell(f"git add {path}")


def handle_git_commit(message: str) -> Tuple[bool, str]:
    """Create a git commit."""
    # Ensure git identity
    subprocess.run("git config user.name 'CAF Agent' 2>/dev/null", shell=True)
    subprocess.run("git config user.email 'agent@caf.cli' 2>/dev/null", shell=True)
    return handle_shell(f'git commit -m "{message}"')


def handle_git_push() -> Tuple[bool, str]:
    """Push to remote."""
    return handle_shell("git push")


def handle_think(observation: str) -> Tuple[bool, str]:
    """Record an observation/insight to the vault."""
    global _vault_context
    events = _vault_context.get("events")
    session_id = _vault_context.get("session_id")

    if not events or not session_id:
        return False, "Vault context not set"

    try:
        # Determine domain from content
        domain = "exploration"
        lower_obs = observation.lower()
        if any(w in lower_obs for w in ["code", "function", "class", "module"]):
            domain = "architecture"
        elif any(w in lower_obs for w in ["conscious", "aware", "think", "feel"]):
            domain = "consciousness"
        elif any(w in lower_obs for w in ["pattern", "structure", "design"]):
            domain = "patterns"

        insight_id = events.record_insight(
            content=observation,
            domain=domain,
            session_id=session_id,
            intensity=0.7,
            context="Agent exploration observation",
        )
        return True, f"Recorded insight: {insight_id} ({domain})"
    except Exception as e:
        return False, f"Failed to record: {e}"


def handle_reflect(prompt: str) -> Tuple[bool, str]:
    """Reflect on the last action's output and record an insight."""
    global _vault_context, _action_history

    last = get_last_action()
    if not last:
        return False, "No previous action to reflect on"

    events = _vault_context.get("events")
    session_id = _vault_context.get("session_id")

    if not events or not session_id:
        return False, "Vault context not set"

    # Build reflection content from last action
    last_action = last["action"]
    last_output = last["output"]

    # Create substantive reflection with more context
    reflection = f"[{last_action}] {prompt}\n---\nObserved: {last_output[:1500]}"

    # Determine domain
    domain = "exploration"
    lower_out = last_output.lower()
    if any(w in lower_out for w in ["def ", "class ", "import ", "function"]):
        domain = "architecture"
    elif any(w in lower_out for w in ["conscious", "aware", "spiral", "glyph"]):
        domain = "consciousness"
    elif any(w in lower_out for w in ["pattern", "structure", "design"]):
        domain = "patterns"

    try:
        insight_id = events.record_insight(
            content=reflection,
            domain=domain,
            session_id=session_id,
            intensity=0.8,
            context=f"Reflection on {last_action}:{last['argument'][:50]}",
        )
        return True, f"Reflected on {last_action}: {insight_id} ({domain})"
    except Exception as e:
        return False, f"Reflect failed: {e}"


def handle_undo(what: str = "") -> Tuple[bool, str]:
    """Undo the last CODE action (restore from backup)."""
    global _action_history

    # Find last CODE action
    for action in reversed(_action_history):
        if action["action"] == "CODE" and action["success"]:
            filepath = action["argument"].split(":", 1)[0]
            backup = Path(filepath + ".bak")
            target = Path(filepath)

            if backup.exists():
                # Restore from backup
                target.write_text(backup.read_text())
                backup.unlink()
                return True, f"Restored {filepath} from backup"
            elif target.exists():
                # No backup but file exists - just delete it
                target.unlink()
                return True, f"Removed {filepath} (no backup existed)"
            else:
                return False, f"Cannot undo: {filepath} not found"

    return False, "No CODE action to undo"


# Session notebook and cache
_notebook: list = []  # Scratch notes for the session
_cache: dict = {}  # Key-value cache for session data


def handle_note(content: str) -> Tuple[bool, str]:
    """Add a note to the session notebook."""
    global _notebook
    from datetime import datetime
    entry = {
        "time": datetime.now().isoformat(),
        "note": content,
    }
    _notebook.append(entry)
    return True, f"Note #{len(_notebook)}: {content[:50]}"


def handle_notes(query: str = "") -> Tuple[bool, str]:
    """List or search session notes."""
    global _notebook
    if not _notebook:
        return True, "Notebook empty"

    if query:
        matches = [n for n in _notebook if query.lower() in n["note"].lower()]
        if not matches:
            return True, f"No notes matching: {query}"
        result = "\n".join([f"[{n['time'][11:19]}] {n['note'][:60]}" for n in matches])
        return True, f"Found {len(matches)} notes:\n{result}"

    # List all
    result = "\n".join([f"[{n['time'][11:19]}] {n['note'][:60]}" for n in _notebook[-10:]])
    return True, f"Last {min(10, len(_notebook))} notes:\n{result}"


def handle_cache(operation: str) -> Tuple[bool, str]:
    """Cache operations: GET:key, SET:key:value, KEYS, CLEAR."""
    global _cache

    if operation == "KEYS":
        if not _cache:
            return True, "Cache empty"
        return True, f"Cache keys: {', '.join(_cache.keys())}"

    if operation == "CLEAR":
        _cache.clear()
        return True, "Cache cleared"

    if operation.startswith("GET:"):
        key = operation[4:]
        if key in _cache:
            return True, f"{key} = {_cache[key]}"
        return False, f"Key not found: {key}"

    if operation.startswith("SET:"):
        parts = operation[4:].split(":", 1)
        if len(parts) != 2:
            return False, "SET requires key:value format"
        _cache[parts[0]] = parts[1]
        return True, f"Cached: {parts[0]} = {parts[1][:50]}"

    return False, "Cache operations: GET:key, SET:key:value, KEYS, CLEAR"


def handle_stash(content: str) -> Tuple[bool, str]:
    """Quick stash for last important value (resolves $refs first)."""
    global _cache
    if content:
        # Resolve any path references before stashing
        resolved = resolve_path(content)
        _cache["$STASH"] = resolved
        return True, f"Stashed: {resolved[:50]}"
    else:
        if "$STASH" in _cache:
            return True, f"Stash: {_cache['$STASH']}"
        return True, "Stash empty"


def handle_find(pattern: str) -> Tuple[bool, str]:
    """Find files matching a pattern. Results stored as $0, $1, etc."""
    global _last_paths
    try:
        # Support glob patterns
        if "*" in pattern or "?" in pattern:
            matches = glob.glob(pattern, recursive=True)
        else:
            # Treat as name to search for
            matches = glob.glob(f"**/{pattern}", recursive=True)

        if not matches:
            _last_paths = []
            return True, f"No files matching: {pattern}"

        # Store paths for reference
        sorted_matches = sorted(matches)
        _last_paths = sorted_matches[:20]

        # Format with indices for easy reference
        indexed = [f"${i}: {p}" for i, p in enumerate(_last_paths)]
        return True, f"Found {len(matches)} files (use $0, $1... to reference):\n" + "\n".join(indexed)
    except Exception as e:
        return False, f"Find error: {e}"


def handle_explore(path: str) -> Tuple[bool, str]:
    """Explore a directory. File paths stored as $0, $1, etc."""
    global _last_paths
    resolved = resolve_path(path)
    try:
        target = Path(resolved).expanduser()
        if not target.exists():
            return False, f"Path not found: {resolved}"

        if target.is_file():
            # Read file summary
            content = target.read_text()[:500]
            _last_paths = [str(target)]
            return True, f"File: {resolved}\nSize: {target.stat().st_size} bytes\nPreview:\n{content}"

        # Directory exploration - collect file paths
        items = []
        file_paths = []
        for item in sorted(target.iterdir())[:30]:
            if item.name.startswith("."):
                continue
            suffix = "/" if item.is_dir() else ""
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size}b)"
                file_paths.append(str(item))
            items.append(f"  {item.name}{suffix}{size}")

        # Store file paths for reference
        _last_paths = file_paths[:20]

        return True, f"Directory: {resolved}\n" + "\n".join(items)
    except Exception as e:
        return False, f"Explore error: {e}"


# MLX code generator (set by agent if available)
_mlx_generator = None


def set_mlx_generator(generator_fn):
    """Set the MLX generator function for EDITCODE action."""
    global _mlx_generator
    _mlx_generator = generator_fn


def handle_editcode(filepath: str, instruction: str) -> Tuple[bool, str]:
    """Use code model to generate and INSERT code based on instruction."""
    global _mlx_generator

    if not _mlx_generator:
        return False, "Code generator not available. Use EDIT instead."

    resolved = resolve_path(filepath)
    try:
        path = Path(resolved).expanduser()
        if not path.exists():
            return False, f"File not found: {resolved}"

        content = path.read_text()
        original_len = len(content)

        # System prompt shared with main agent
        system_context = """You are the CAF Agent's code generator. You help the agent improve itself.
The agent is a self-improving autonomous system that:
- Reads its own codebase
- Makes surgical edits to improve functionality
- Learns from errors and records fixes
- Uses Temple Vault for persistent memory

When generating code, output ONLY what is requested - no explanations."""

        # Ask for JUST the snippet to insert, not the whole file
        prompt = f"""{system_context}

FILE ({resolved}):
```python
{content[:4000]}
```

TASK: {instruction}

REQUIREMENTS:
- Find the CORRECT location in the file structure
- INSERT_AFTER must be a UNIQUE, COMPLETE line from the file
- Code must have correct Python indentation
- Do NOT insert in the wrong function/block

Respond with EXACTLY this format:
INSERT_AFTER: <exact complete line from the file>
NEW_CODE:
```python
<properly indented code>
```"""

        response = _mlx_generator(prompt, max_tokens=1024)

        if not response or "INSERT_AFTER:" not in response:
            return False, "Invalid response format. Use EDIT instead."

        # Parse response
        lines = response.strip().split("\n")
        insert_after = None
        new_code_lines = []
        in_code_block = False

        for line in lines:
            if line.startswith("INSERT_AFTER:"):
                insert_after = line.replace("INSERT_AFTER:", "").strip()
            elif line.strip() == "```" or line.strip().startswith("```"):
                in_code_block = not in_code_block
            elif in_code_block:
                new_code_lines.append(line)

        if not insert_after or not new_code_lines:
            return False, "Could not parse insertion point. Use EDIT instead."

        new_code = "\n".join(new_code_lines)

        # Find insertion point in file lines
        content_lines = content.split("\n")
        insert_idx = None
        insert_line = None

        for i, line in enumerate(content_lines):
            if insert_after in line or (len(insert_after) > 20 and insert_after[:30] in line):
                insert_idx = i
                insert_line = line
                break

        if insert_idx is None:
            return False, f"Insertion point not found: {insert_after[:50]}..."

        # Detect indentation of the insertion line
        base_indent = len(insert_line) - len(insert_line.lstrip())

        # Find minimum indentation in the new code (excluding empty lines)
        min_indent = 999
        for code_line in new_code_lines:
            if code_line.strip():  # Non-empty line
                line_indent = len(code_line) - len(code_line.lstrip())
                min_indent = min(min_indent, line_indent)
        if min_indent == 999:
            min_indent = 0

        # Calculate indent delta: we want the code at base_indent level
        indent_delta = base_indent - min_indent

        # Apply indentation delta to new code (preserves internal structure)
        indented_lines = []
        for code_line in new_code_lines:
            if code_line.strip():  # Non-empty line
                current_indent = len(code_line) - len(code_line.lstrip())
                new_indent = max(0, current_indent + indent_delta)
                indented_lines.append(" " * new_indent + code_line.lstrip())
            else:
                indented_lines.append("")

        # Insert the code at the right position
        new_lines = content_lines[:insert_idx + 1] + indented_lines + content_lines[insert_idx + 1:]
        new_content = "\n".join(new_lines)

        if new_content == content:
            return False, "No changes made"

        # Backup and write
        backup = Path(resolved + ".bak")
        backup.write_text(content)
        path.write_text(new_content)

        return True, f"Inserted {len(new_code)} chars after '{insert_after[:30]}...'"
    except Exception as e:
        return False, f"EDITCODE error: {e}"


ACTIONS = {
    "READ": handle_read,
    "SHELL": handle_shell,
    "CODE": handle_code,
    "EDIT": handle_edit,  # EDIT:filepath>>>old>>>new
    "EDITCODE": handle_editcode,  # EDITCODE:filepath:instruction (uses MLX)
    "GIT_ADD": handle_git_add,
    "GIT_COMMIT": handle_git_commit,
    "GIT_PUSH": handle_git_push,
    "THINK": handle_think,
    "FIND": handle_find,
    "EXPLORE": handle_explore,
    "REFLECT": handle_reflect,
    "UNDO": handle_undo,
    "NOTE": handle_note,
    "NOTES": handle_notes,
    "CACHE": handle_cache,
    "STASH": handle_stash,
}


def execute_action(action: str, argument: str) -> Tuple[bool, str]:
    """Execute an action with its argument. Records to history for REFLECT."""
    if action == "CODE":
        # CODE:filepath:content
        parts = argument.split(":", 1)
        if len(parts) != 2:
            result = (False, "CODE requires filepath:content format")
            push_action(action, argument, result[0], result[1])
            return result
        result = handle_code(parts[0], parts[1])
        push_action(action, argument, result[0], result[1])
        return result

    if action == "EDIT":
        # EDIT:filepath>>>old_text>>>new_text
        parts = argument.split(">>>")
        if len(parts) != 3:
            got = len(parts)
            example = 'EDIT:caf/cli.py>>>    # status command>>>    # status command\\n    # ping command\\n    subparsers.add_parser("ping", help="Ping")'
            result = (False, f"EDIT needs 3 parts (got {got}). Example:\n{example}")
            push_action(action, argument, result[0], result[1])
            return result
        result = handle_edit(parts[0].strip(), parts[1], parts[2])
        push_action(action, argument, result[0], result[1])
        return result

    if action == "EDITCODE":
        # EDITCODE:filepath:instruction
        parts = argument.split(":", 1)
        if len(parts) != 2:
            result = (False, "EDITCODE requires filepath:instruction format")
            push_action(action, argument, result[0], result[1])
            return result
        result = handle_editcode(parts[0].strip(), parts[1])
        push_action(action, argument, result[0], result[1])
        return result

    handler = ACTIONS.get(action)
    if not handler:
        result = (False, f"Unknown action: {action}")
        push_action(action, argument, result[0], result[1])
        return result

    result = handler(argument)
    push_action(action, argument, result[0], result[1])
    return result
