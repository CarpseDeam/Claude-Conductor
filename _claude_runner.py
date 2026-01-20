
import subprocess
import json
import sys
import traceback

try:
    print("=" * 60)
    print("CLAUDE CODE - LIVE")
    print("=" * 60)
    print()

    prompt = open("_claude_prompt.txt", "r", encoding="utf-8").read()
    print(f"Task: {prompt[:100]}...")
    print()

    cmd = ["claude", "-p", prompt, "--output-format", "stream-json"]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            msg_type = data.get("type", "")
            
            if msg_type == "assistant":
                msg = data.get("message", {})
                content = msg.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        print(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        tool = block.get("name", "unknown")
                        inp = block.get("input", {})
                        if tool in ("Read", "Write", "Edit"):
                            path = inp.get("file_path", inp.get("path", ""))
                            print(f"[{tool}] {path}")
                        elif tool == "Bash":
                            cmd_str = inp.get("command", "")[:50]
                            print(f"[Bash] {cmd_str}...")
                        else:
                            print(f"[{tool}]")
            elif msg_type == "result":
                print()
                print("=" * 60)
                print("COMPLETE")
                print("=" * 60)
        except json.JSONDecodeError:
            print(line)

    process.wait()
    print(f"\nExit code: {process.returncode}")
    
except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()

input("\nPress Enter to close...")
